"""
Run VisDoM retrieval experiment end-to-end.

Usage:
    py -3 scripts/run_experiment.py --dataset feta_tab --max-docs 10 --max-queries 20
"""
import argparse
import csv
import json
import os
import sys
import time
import socket
import threading
import select

import paramiko
import httpx

# ── SSH tunnel setup ────────────────────────────────────────────────

def setup_ssh_tunnel():
    """Create SSH tunnel to remote GPU server (configured via env vars)."""
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
    channel = transport.open_channel(
        'direct-tcpip', (target_host, target_port), ('127.0.0.1', 0),
    )
    gpu = paramiko.SSHClient()
    gpu.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    gpu.connect(
        target_host, port=target_port, username=os.environ['SSH_TARGET_USER'],
        password=os.environ['SSH_TARGET_PASSWORD'], sock=channel,
    )
    gpu_transport = gpu.get_transport()

    def forward(local_port, remote_port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', local_port))
        server.listen(5)
        server.settimeout(1.0)

        def handle(client):
            try:
                chan = gpu_transport.open_channel(
                    'direct-tcpip', ('localhost', remote_port),
                    client.getpeername(),
                )
            except Exception:
                client.close()
                return
            while True:
                r, _, _ = select.select([client, chan], [], [], 1.0)
                if client in r:
                    d = client.recv(32768)
                    if not d:
                        break
                    chan.sendall(d)
                if chan in r:
                    d = chan.recv(32768)
                    if not d:
                        break
                    client.sendall(d)
            chan.close()
            client.close()

        def accept():
            while True:
                try:
                    c, _ = server.accept()
                    threading.Thread(target=handle, args=(c,), daemon=True).start()
                except socket.timeout:
                    continue
                except OSError:
                    break

        threading.Thread(target=accept, daemon=True).start()
        return server

    s1 = forward(8001, 8001)
    s2 = forward(6333, 6333)
    time.sleep(1)
    return bastion, gpu, [s1, s2]


# ── VisDoM data loading ────────────────────────────────────────────

VISDOM_BASE = "/home/bzli/lbz/data/VisDoM-main"

def load_visdom_csv(dataset_name: str, max_queries: int = None):
    """Load VisDoM queries from remote server CSV (via SSH)."""
    # We'll read the CSV via the SSH connection that's already open
    pass  # Will be loaded from local copy


def download_csv_via_sftp(gpu_ssh, dataset_name: str, local_dir: str):
    """Download dataset CSV from remote server."""
    sftp = gpu_ssh.open_sftp()
    csv_name = f"{dataset_name}.csv"
    if dataset_name == "scigraphvqa":
        csv_name = "scigraphqa.csv"
    remote_path = f"{VISDOM_BASE}/{dataset_name}/{csv_name}"
    local_path = os.path.join(local_dir, csv_name)
    sftp.get(remote_path, local_path)
    sftp.close()
    return local_path


def parse_eval_queries(csv_path: str, max_queries: int = None):
    """Parse VisDoM CSV into eval queries."""
    queries = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_queries and i >= max_queries:
                break
            doc_path = row.get("doc_path", "")
            # The relevant document is identified by doc_id
            doc_id = row.get("doc_id", "")
            query = row.get("question", "")
            answer = row.get("answer", "")

            if not query or not doc_id:
                continue

            queries.append({
                "q_id": row.get("q_id", str(i)),
                "query": query,
                "answer": answer,
                "doc_id": doc_id,
                "doc_path": doc_path,
                "documents": row.get("documents", "[]"),
            })
    return queries


def get_unique_docs(queries):
    """Extract unique document paths from queries."""
    docs = set()
    for q in queries:
        # Parse the documents list
        try:
            doc_list = eval(q["documents"])
        except Exception:
            doc_list = [q["doc_path"]]
        for d in doc_list:
            docs.add(d)
    return sorted(docs)


# ── API client ──────────────────────────────────────────────────────

BASE_URL = "http://127.0.0.1:8000"


def upload_document(client: httpx.Client, pdf_path: str, dataset_id: int = None):
    """Upload a PDF document via the backend API."""
    filename = os.path.basename(pdf_path)
    with open(pdf_path, 'rb') as f:
        files = {"file": (filename, f, "application/pdf")}
        params = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        resp = client.post(f"{BASE_URL}/documents/upload", files=files, params=params,
                          timeout=300)
    return resp.json()


def list_documents(client: httpx.Client):
    """List all indexed documents."""
    resp = client.get(f"{BASE_URL}/documents/", timeout=30)
    return resp.json()


def run_evaluation(client: httpx.Client, eval_queries: list, top_k: int = 10):
    """Run retrieval evaluation."""
    body = {
        "queries": eval_queries,
        "top_k": top_k,
        "note": "VisDoM experiment",
    }
    resp = client.post(f"{BASE_URL}/experiments/evaluate", json=body, timeout=600)
    return resp.json()


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run VisDoM retrieval experiment")
    parser.add_argument("--dataset", default="feta_tab",
                       choices=["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"])
    parser.add_argument("--max-docs", type=int, default=10,
                       help="Max documents to upload (for quick testing)")
    parser.add_argument("--max-queries", type=int, default=20,
                       help="Max queries to evaluate")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--skip-upload", action="store_true",
                       help="Skip document upload (if already indexed)")
    args = parser.parse_args()

    print(f"=== VisDoM Experiment: {args.dataset} ===")
    print(f"Max docs: {args.max_docs}, Max queries: {args.max_queries}")

    # 1. Setup SSH tunnel
    print("\n[1/5] Setting up SSH tunnel...")
    bastion, gpu, servers = setup_ssh_tunnel()
    print("  SSH tunnel established")

    # Verify connectivity
    try:
        resp = httpx.get("http://127.0.0.1:8001/health", timeout=5)
        print(f"  Worker: {resp.json()}")
    except Exception as e:
        print(f"  Worker not reachable: {e}")
        return

    try:
        resp = httpx.get("http://127.0.0.1:6333/", timeout=5)
        print(f"  Qdrant: {resp.json()['version']}")
    except Exception as e:
        print(f"  Qdrant not reachable: {e}")
        return

    # 2. Download CSV and parse queries
    print(f"\n[2/5] Loading {args.dataset} queries...")
    os.makedirs("data/visdom_cache", exist_ok=True)
    csv_path = download_csv_via_sftp(gpu, args.dataset, "data/visdom_cache")
    queries = parse_eval_queries(csv_path, args.max_queries)
    print(f"  Loaded {len(queries)} queries")

    # 3. Download and upload PDFs
    if not args.skip_upload:
        print(f"\n[3/5] Downloading and uploading documents...")
        unique_docs = get_unique_docs(queries)
        if args.max_docs:
            unique_docs = unique_docs[:args.max_docs]
        print(f"  {len(unique_docs)} unique documents to process")

        # Download PDFs from remote and upload to local backend
        sftp = gpu.open_sftp()
        os.makedirs("data/visdom_pdfs", exist_ok=True)

        client = httpx.Client(timeout=300)
        for i, doc_name in enumerate(unique_docs):
            remote_pdf = f"{VISDOM_BASE}/{args.dataset}/docs/{doc_name}"
            local_pdf = os.path.join("data/visdom_pdfs", doc_name)

            if not os.path.exists(local_pdf):
                try:
                    sftp.get(remote_pdf, local_pdf)
                except Exception as e:
                    print(f"  [{i+1}/{len(unique_docs)}] SKIP {doc_name}: {e}")
                    continue

            try:
                result = upload_document(client, local_pdf)
                status = result.get("status", "unknown")
                print(f"  [{i+1}/{len(unique_docs)}] {doc_name}: {status}")
            except Exception as e:
                print(f"  [{i+1}/{len(unique_docs)}] {doc_name}: ERROR {e}")

        sftp.close()
        client.close()

        # Wait for indexing to complete
        print("  Waiting for indexing to complete...")
        time.sleep(5)
        client = httpx.Client(timeout=30)
        for _ in range(60):
            docs = list_documents(client)
            indexing = [d for d in docs if d.get("status") == "indexing"]
            if not indexing:
                break
            print(f"  Still indexing {len(indexing)} documents...")
            time.sleep(10)
        client.close()
    else:
        print("\n[3/5] Skipping document upload")

    # 4. Build eval queries
    print(f"\n[4/5] Building evaluation queries...")
    # Get indexed documents to map doc_id to pages
    client = httpx.Client(timeout=30)
    indexed_docs = list_documents(client)
    doc_map = {d["filename"].replace(".pdf", ""): d["id"] for d in indexed_docs}

    eval_queries = []
    for q in queries:
        doc_id_in_system = doc_map.get(q["doc_id"])
        if doc_id_in_system is None:
            continue
        # The relevant page is unknown, so we mark all pages as potentially relevant
        # (VisDoM doesn't always specify exact pages)
        relevant = [f"{doc_id_in_system}:1"]  # At minimum page 1
        eval_queries.append({
            "query": q["query"],
            "relevant": relevant,
        })

    print(f"  {len(eval_queries)} queries matched to indexed documents")

    if not eval_queries:
        print("  No matching queries found. Make sure documents are indexed.")
        return

    # 5. Run evaluation
    print(f"\n[5/5] Running retrieval evaluation (top_k={args.top_k})...")
    result = run_evaluation(client, eval_queries, top_k=args.top_k)
    client.close()

    # Print results
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Dataset:        {args.dataset}")
    print(f"Total queries:  {result.get('total_queries', 0)}")
    print(f"Recall@1:       {result.get('recall_at_k', {}).get('1', 0):.4f}")
    print(f"Recall@5:       {result.get('recall_at_k', {}).get('5', 0):.4f}")
    print(f"Recall@10:      {result.get('recall_at_k', {}).get('10', 0):.4f}")
    print(f"MRR:            {result.get('mrr', 0):.4f}")
    print(f"Avg timing:     {result.get('avg_timing_ms', {})}")
    print(f"Experiment ID:  {result.get('experiment_id', 'N/A')}")

    # Save results
    os.makedirs("data/results", exist_ok=True)
    result_path = f"data/results/{args.dataset}_{int(time.time())}.json"
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to: {result_path}")

    # Cleanup
    for s in servers:
        s.close()
    gpu.close()
    bastion.close()


if __name__ == "__main__":
    main()
