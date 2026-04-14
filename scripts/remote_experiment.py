"""
Run VisDoM experiment entirely on the remote GPU server.

This script:
1. Connects to the remote server via SSH
2. Starts the backend API server (connects to local worker + qdrant)
3. Uploads documents from VisDoM dataset
4. Runs retrieval evaluation
5. Downloads results to local machine

Usage:
    py -3 scripts/remote_experiment.py --dataset feta_tab --max-docs 10 --max-queries 20
"""
import argparse
import json
import os
import sys
import time

import paramiko


def get_connection():
    bastion = paramiko.SSHClient()
    bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    bastion.connect(
        os.environ['SSH_BASTION_HOST'],
        port=int(os.environ.get('SSH_BASTION_PORT', '22')),
        username=os.environ['SSH_BASTION_USER'],
        key_filename=os.environ['SSH_BASTION_KEY'],
    )
    transport = bastion.get_transport()
    target_host = os.environ['SSH_TARGET_HOST']
    target_port = int(os.environ.get('SSH_TARGET_PORT', '22'))
    channel = transport.open_channel('direct-tcpip', (target_host, target_port), ('127.0.0.1', 0))
    gpu = paramiko.SSHClient()
    gpu.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    gpu.connect(target_host, port=target_port, username=os.environ['SSH_TARGET_USER'],
                password=os.environ['SSH_TARGET_PASSWORD'], sock=channel)
    return bastion, gpu


def run(gpu, cmd, timeout=300, show=True):
    stdin, stdout, stderr = gpu.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if show:
        if out.strip():
            print(out[-2000:])
        if err.strip() and 'WARNING' not in err and 'PytestDeprecation' not in err:
            print('ERR:', err[-500:])
    return out, err


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="feta_tab",
                       choices=["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"])
    parser.add_argument("--max-docs", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    print(f"=== VisDoM Remote Experiment: {args.dataset} ===")
    bastion, gpu = get_connection()

    # Write the experiment runner script to remote
    experiment_script = f'''#!/usr/bin/env python3
"""Run experiment on remote server."""
import asyncio
import csv
import json
import os
import sys
import time

# Add project to path
sys.path.insert(0, "/home/bzli/mrag_app")

VISDOM_BASE = "/home/bzli/lbz/data/VisDoM-main"
DATASET = "{args.dataset}"
MAX_DOCS = {args.max_docs}
MAX_QUERIES = {args.max_queries}
TOP_K = {args.top_k}
SKIP_UPLOAD = {args.skip_upload}

async def main():
    from qdrant_client import AsyncQdrantClient
    from backend.core.config import load_config
    from backend.core.pipeline import PipelineManager
    from backend.services.cache import DiskCache
    from backend.services.document_service import DocumentService
    from backend.services.experiment_service import ExperimentService
    from backend.services.worker_client import WorkerClient
    from backend.services.evaluation import compute_recall_at_k, compute_mrr
    from backend.strategies import ALL_REGISTRIES, import_all_strategies

    # Initialize
    import_all_strategies()

    worker_client = WorkerClient(host="localhost", port=8001, timeout=300)
    qdrant_client = AsyncQdrantClient(host="localhost", port=6333)

    # Ensure collection
    from qdrant_client import models
    try:
        await qdrant_client.get_collection("documents")
        print("Collection exists")
    except Exception:
        print("Creating collection...")
        await qdrant_client.create_collection(
            collection_name="documents",
            vectors_config=models.VectorParams(
                size=128,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM,
                ),
            ),
        )

    query_cache = DiskCache(path="/home/bzli/mrag_app/data/cache/query", enabled=True)
    gen_cache = DiskCache(path="/home/bzli/mrag_app/data/cache/generation", enabled=True)

    deps = {{
        "worker_client": worker_client,
        "qdrant_client": qdrant_client,
        "collection_name": "documents",
        "images_dir": "/home/bzli/mrag_app/data/images",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "query_cache": query_cache,
        "generation_cache": gen_cache,
    }}

    config = {{
        "processor": "page_screenshot",
        "document_encoder": "colpali",
        "query_encoder": "colpali",
        "retriever": "multi_vector",
        "reranker": None,
        "generator": "openai_gpt4o",
    }}

    pipeline_manager = PipelineManager(ALL_REGISTRIES, deps=deps)
    pipeline_manager.set_pipeline(config)
    pipeline = pipeline_manager.pipeline

    os.makedirs("/home/bzli/mrag_app/data/uploads", exist_ok=True)
    os.makedirs("/home/bzli/mrag_app/data/images", exist_ok=True)

    doc_svc = DocumentService(
        upload_dir="/home/bzli/mrag_app/data/uploads",
        pipeline=pipeline,
    )

    exp_svc = ExperimentService(
        db_path="/home/bzli/mrag_app/data/uploads/experiments.db",
    )

    # Load VisDoM CSV
    csv_name = f"{{DATASET}}.csv"
    if DATASET == "scigraphvqa":
        csv_name = "scigraphqa.csv"
    csv_path = f"{{VISDOM_BASE}}/{{DATASET}}/{{csv_name}}"

    queries = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if MAX_QUERIES and i >= MAX_QUERIES:
                break
            q = row.get("question", "")
            doc_id = row.get("doc_id", "")
            doc_path = row.get("doc_path", "")
            documents_str = row.get("documents", "[]")
            if not q or not doc_id:
                continue
            queries.append({{
                "query": q,
                "doc_id": doc_id,
                "doc_path": doc_path,
                "documents": documents_str,
            }})

    print(f"Loaded {{len(queries)}} queries from {{DATASET}}")

    # Get unique docs from queries
    all_docs = set()
    for q in queries:
        try:
            doc_list = eval(q["documents"])
        except:
            doc_list = [q["doc_path"]]
        for d in doc_list:
            all_docs.add(d)
    all_docs = sorted(all_docs)[:MAX_DOCS]
    print(f"{{len(all_docs)}} unique documents to index")

    # Upload and index documents
    if not SKIP_UPLOAD:
        for i, doc_name in enumerate(all_docs):
            src = f"{{VISDOM_BASE}}/{{DATASET}}/docs/{{doc_name}}"
            if not os.path.exists(src):
                print(f"  [{{i+1}}/{{len(all_docs)}}] SKIP {{doc_name}}: not found")
                continue

            # Check if already indexed
            existing = [d for d in doc_svc.list_documents() if d.filename == doc_name]
            if existing and existing[0].status == "completed":
                print(f"  [{{i+1}}/{{len(all_docs)}}] {{doc_name}} already indexed, skipping")
                continue

            try:
                with open(src, 'rb') as f:
                    content = f.read()
                doc_info = await doc_svc.upload(doc_name, content)
                print(f"  [{{i+1}}/{{len(all_docs)}}] Indexing {{doc_name}}...")
                await doc_svc.index_document(doc_info.id)
                print(f"  [{{i+1}}/{{len(all_docs)}}] {{doc_name}} indexed")
            except Exception as e:
                print(f"  [{{i+1}}/{{len(all_docs)}}] {{doc_name}} ERROR: {{e}}")
                import traceback
                traceback.print_exc()

    # Build eval queries
    indexed = doc_svc.list_documents()
    doc_map = {{d.filename.replace('.pdf', ''): d.id for d in indexed}}
    print(f"\\nIndexed documents: {{len(doc_map)}}")

    eval_queries = []
    for q in queries:
        sys_doc_id = doc_map.get(q["doc_id"])
        if sys_doc_id is None:
            continue
        # Mark page 1 as relevant (VisDoM doesn't always specify pages)
        eval_queries.append({{
            "query": q["query"],
            "relevant": [f"{{sys_doc_id}}:1"],
        }})

    print(f"Matched {{len(eval_queries)}} eval queries to indexed docs")

    if not eval_queries:
        print("No matching queries! Exiting.")
        return

    # Run evaluation
    print(f"\\nRunning retrieval evaluation (top_k={{TOP_K}})...")
    recall_sums = {{1: 0.0, 5: 0.0, 10: 0.0}}
    mrr_sum = 0.0
    timing_sums = {{}}
    per_query = []
    n = len(eval_queries)

    for i, eq in enumerate(eval_queries):
        t0 = time.time()
        bundle = await pipeline.retrieve(eq["query"], top_k=TOP_K)
        elapsed = (time.time() - t0) * 1000

        # Check if any result matches the relevant doc (any page)
        relevant_doc_id = eq["relevant"][0].split(":")[0]
        retrieved_ids = [f"{{r.document_id}}:{{r.page_number}}" for r in bundle.results]
        retrieved_doc_ids = [r.document_id for r in bundle.results]

        # Document-level recall (did we retrieve any page of the right doc?)
        doc_hit = 1.0 if relevant_doc_id in retrieved_doc_ids else 0.0
        doc_hit_5 = 1.0 if relevant_doc_id in retrieved_doc_ids[:5] else 0.0
        doc_hit_1 = 1.0 if relevant_doc_id in retrieved_doc_ids[:1] else 0.0

        # MRR at document level
        rr = 0.0
        for rank, did in enumerate(retrieved_doc_ids):
            if did == relevant_doc_id:
                rr = 1.0 / (rank + 1)
                break

        recall_sums[1] += doc_hit_1
        recall_sums[5] += doc_hit_5
        recall_sums[10] += doc_hit

        mrr_sum += rr

        for tk, tv in bundle.timing.items():
            timing_sums[tk] = timing_sums.get(tk, 0.0) + tv

        per_query.append({{
            "query": eq["query"][:80],
            "relevant_doc": relevant_doc_id,
            "retrieved_docs": retrieved_doc_ids[:5],
            "doc_recall@10": doc_hit,
            "rr": rr,
            "latency_ms": elapsed,
        }})

        status = "HIT" if doc_hit > 0 else "MISS"
        print(f"  [{{i+1}}/{{n}}] {{status}} (RR={{rr:.2f}}, {{elapsed:.0f}}ms) {{eq['query'][:60]}}...")

    # Compute averages
    results = {{
        "dataset": DATASET,
        "total_queries": n,
        "max_docs": MAX_DOCS,
        "recall_at_1": recall_sums[1] / n if n else 0,
        "recall_at_5": recall_sums[5] / n if n else 0,
        "recall_at_10": recall_sums[10] / n if n else 0,
        "mrr": mrr_sum / n if n else 0,
        "avg_timing_ms": {{k: v / n for k, v in timing_sums.items()}} if n else {{}},
        "per_query": per_query,
    }}

    print("\\n" + "=" * 60)
    print(f"RESULTS: {{DATASET}}")
    print("=" * 60)
    print(f"Documents indexed: {{len(doc_map)}}")
    print(f"Queries evaluated: {{n}}")
    print(f"Recall@1:  {{results['recall_at_1']:.4f}}")
    print(f"Recall@5:  {{results['recall_at_5']:.4f}}")
    print(f"Recall@10: {{results['recall_at_10']:.4f}}")
    print(f"MRR:       {{results['mrr']:.4f}}")
    print(f"Avg timing: {{results['avg_timing_ms']}}")

    # Save results
    os.makedirs("/home/bzli/mrag_app/data/results", exist_ok=True)
    result_path = f"/home/bzli/mrag_app/data/results/{{DATASET}}_{{int(time.time())}}.json"
    with open(result_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\\nResults saved to: {{result_path}}")

asyncio.run(main())
'''

    # Upload experiment script
    sftp = gpu.open_sftp()
    with sftp.open('/home/bzli/mrag_app/run_exp.py', 'w') as f:
        f.write(experiment_script)
    sftp.close()
    print("Experiment script uploaded")

    # Install missing deps on remote (pdf2image for page screenshot processor)
    print("\nEnsuring dependencies...")
    run(gpu, (
        'source ~/miniconda3/etc/profile.d/conda.sh && '
        'conda activate mrag_worker && '
        'pip install pdf2image pdfplumber rank-bm25 2>&1 | tail -3'
    ))

    # Check if poppler is available
    out, _ = run(gpu, 'which pdftoppm 2>/dev/null || echo "no poppler"', show=False)
    if 'no poppler' in out:
        print("Installing poppler-utils...")
        run(gpu, 'sudo apt-get install -y poppler-utils 2>&1 | tail -3 || conda install -c conda-forge poppler -y 2>&1 | tail -3')

    # Run the experiment
    print(f"\nRunning experiment on remote server...")
    print("=" * 60)

    exp_cmd = (
        'cd /home/bzli/mrag_app && '
        'source ~/miniconda3/etc/profile.d/conda.sh && '
        'conda activate mrag_worker && '
        'HF_ENDPOINT=https://hf-mirror.com '
        'python run_exp.py 2>&1'
    )
    stdin, stdout, stderr = gpu.exec_command(exp_cmd, timeout=600)
    for line in iter(stdout.readline, ''):
        print(line, end='')
    err = stderr.read().decode()
    if err.strip():
        print('STDERR:', err[-500:])

    # Download results
    print("\n\nDownloading results...")
    sftp = gpu.open_sftp()
    os.makedirs("data/results", exist_ok=True)
    try:
        remote_results = '/home/bzli/mrag_app/data/results'
        for f_name in sftp.listdir(remote_results):
            if f_name.endswith('.json') and args.dataset in f_name:
                sftp.get(f'{remote_results}/{f_name}', f'data/results/{f_name}')
                print(f"  Downloaded: {f_name}")
    except Exception as e:
        print(f"  Could not download results: {e}")
    sftp.close()

    gpu.close()
    bastion.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
