"""QA v3 — sequential, no concurrent indexing.

Tests every endpoint with realistic queries; isolates region indexing
to its own (optional) phase so the SSH tunnel doesn't get poisoned by
concurrent traffic.
"""
import asyncio, io, json, os, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
for v in ("NO_PROXY", "no_proxy"):
    os.environ[v] = (os.environ.get(v, "") + ",localhost,127.0.0.1").lstrip(",")
for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[v] = ""
import httpx

BASE = "http://127.0.0.1:8080"


class QA:
    def __init__(self):
        self.passes = []
        self.warns = []
        self.fails = []

    def OK(self, name, detail=""):
        self.passes.append(name)
        print(f"  ✓ {name}{(' — ' + detail) if detail else ''}")

    def WARN(self, name, detail=""):
        self.warns.append((name, detail))
        print(f"  ! {name}{(' — ' + detail) if detail else ''}")

    def FAIL(self, name, detail=""):
        self.fails.append((name, detail))
        print(f"  ✗ {name}{(' — ' + detail) if detail else ''}")


def banner(s):
    print(f"\n{'='*70}\n{s}\n{'='*70}")


async def main(test_indexing: bool = False):
    qa = QA()
    async with httpx.AsyncClient(trust_env=False, timeout=300) as c:
        banner("[1] Health endpoints")
        for path in ["/api/health", "/api/lab/info", "/api/lab/health"]:
            r = await c.get(f"{BASE}{path}")
            if r.status_code == 200:
                qa.OK(path, f"{r.status_code}")
            else:
                qa.FAIL(path, f"{r.status_code}")
        h = (await c.get(f"{BASE}/api/lab/health")).json()
        for k in ("bm25_ready", "layout_ready", "sklearn_available",
                  "region_collection_ready", "main_pipeline_ok"):
            (qa.OK if h[k] else qa.WARN)(f"lab.{k}", str(h[k]))

        banner("[2] Documents")
        docs = (await c.get(f"{BASE}/api/documents")).json()
        completed = [d for d in docs if d["status"] == "completed"]
        qa.OK("documents.list", f"{len(docs)} total / {len(completed)} completed")
        if not completed:
            qa.FAIL("docs", "no completed docs — cannot test query path")
            return qa

        first = completed[0]
        # Document layout endpoint
        r = await c.get(f"{BASE}/api/documents/{first['id']}/layout/1")
        if r.status_code == 200:
            l = r.json()
            qa.OK("layout/1", f"{len(l.get('elements', []))} elements")
        elif r.status_code == 404:
            qa.WARN("layout/1", "404 — endpoint may not exist or doc has no layout")
        else:
            qa.FAIL("layout/1", f"status={r.status_code}")

        banner("[3] Validation rejection (empty query)")
        for path in ["/api/query", "/api/retrieve", "/api/lab/hybrid",
                     "/api/lab/visa", "/api/lab/gmm", "/api/lab/region/query"]:
            r = await c.post(f"{BASE}{path}", json={"query": "", "top_k": 5})
            if r.status_code in (400, 422):
                qa.OK(f"{path} 400/422 on empty")
            else:
                qa.FAIL(path + " empty", f"{r.status_code}")

        banner("[4] /api/retrieve (no LLM, fast)")
        Q1 = "文档检索"
        t = time.time()
        r = await c.post(f"{BASE}/api/retrieve", json={"query": Q1, "top_k": 5})
        if r.status_code == 200:
            d = r.json()
            qa.OK("retrieve", f"{len(d['results'])} results in {(time.time()-t)*1000:.0f}ms")
        else:
            qa.FAIL("retrieve", f"{r.status_code}")

        banner("[5] /api/lab/hybrid (3 channels)")
        r = await c.post(f"{BASE}/api/lab/hybrid",
                         json={"query": Q1, "top_k": 3, "candidates": 15})
        if r.status_code == 200:
            d = r.json()
            chs = {c["channel"]: c for c in d["channels"]}
            for name in ("bm25", "colpali", "rrf"):
                if name in chs:
                    qa.OK(f"hybrid.{name}", f"{len(chs[name]['results'])} results")
                else:
                    qa.FAIL(f"hybrid.{name}", "missing")
        else:
            qa.FAIL("hybrid", f"{r.status_code}")

        banner("[6] /api/lab/gmm (sklearn)")
        r = await c.post(f"{BASE}/api/lab/gmm",
                         json={"query": Q1, "top_k": 5, "candidates": 20})
        if r.status_code == 200:
            d = r.json()
            qa.OK("gmm", f"fixed={d['fixed_top_k']} dynamic={d['dynamic_top_k']} cutoff={d['cutoff_score']:.3f}")
            if len(d["components"]) == 2:
                qa.OK("gmm.components", "2 fitted")
            else:
                qa.WARN("gmm.components", f"{len(d['components'])} (expected 2)")
        else:
            qa.FAIL("gmm", f"{r.status_code}")

        banner("[7] /api/lab/region/query (existing collection)")
        r = await c.post(f"{BASE}/api/lab/region/query",
                         json={"query": Q1, "top_k": 5})
        if r.status_code == 200:
            d = r.json()
            qa.OK("region.query", f"{len(d['hits'])} hits, note: {d['note'][:60]}")
        else:
            qa.FAIL("region.query", f"{r.status_code}")

        banner("[8] /api/lab/visa (with citations)")
        Q2 = "文档结构化解析的方法"
        r = await c.post(f"{BASE}/api/lab/visa", json={"query": Q2, "top_k": 3})
        if r.status_code == 200:
            d = r.json()
            cites = sorted({er['citation'] for er in d['evidence_regions']})
            qa.OK("visa", f"answer={len(d['answer'])}c regions={len(d['evidence_regions'])} cites={cites}")
            # All sources should have at least one region
            if len(set(cites)) == len(d['sources']):
                qa.OK("visa.full_coverage", f"all {len(d['sources'])} sources cited")
            else:
                qa.WARN("visa.coverage", f"only {len(set(cites))}/{len(d['sources'])} sources cited")
            # Backfill should fire if needed
            n_regions = len(d['evidence_regions'])
            n_sources = len(d['sources'])
            if n_regions >= n_sources:
                qa.OK("visa.regions_per_source", f">= {n_sources}")
            else:
                qa.FAIL("visa.regions_per_source", f"{n_regions} < {n_sources}")
        else:
            qa.FAIL("visa", f"{r.status_code} body={r.text[:200]}")

        banner("[9] /api/query (full pipeline)")
        Q3 = "什么是注意力机制"
        r = await c.post(f"{BASE}/api/query", json={"query": Q3, "top_k": 3})
        if r.status_code == 200:
            d = r.json()
            qa.OK("query", f"answer={len(d['answer'])}c, sources={len(d['sources'])}")
        else:
            qa.FAIL("query", f"{r.status_code}")

        banner("[10] Image fetch + placeholder")
        r = await c.get(f"{BASE}/api/images/{first['id']}/page_1.png")
        if r.status_code == 200 and len(r.content) > 100:
            qa.OK("image.real", f"{len(r.content)} bytes")
        else:
            qa.FAIL("image.real", f"{r.status_code} {len(r.content)}b")
        r = await c.get(f"{BASE}/api/images/_nope_/page_99.png")
        if r.status_code == 200 and len(r.content) > 100:
            qa.OK("image.placeholder", f"{len(r.content)} bytes")
        else:
            qa.FAIL("image.placeholder", f"{r.status_code}")

        banner("[11] Datasets")
        r = await c.get(f"{BASE}/api/datasets")
        qa.OK("datasets.list", f"status={r.status_code}") if r.status_code == 200 else qa.FAIL("datasets", f"{r.status_code}")

        banner("[12] Experiments history")
        r = await c.get(f"{BASE}/api/experiments/history?limit=5")
        if r.status_code == 200:
            qa.OK("exp.history", f"{len(r.json())} records")
        else:
            qa.FAIL("exp.history", f"{r.status_code}")

        banner("[13] Cache stats")
        r = await c.get(f"{BASE}/api/cache/stats")
        if r.status_code == 200:
            qa.OK("cache.stats", str(r.json())[:80])
        else:
            qa.FAIL("cache.stats", f"{r.status_code}")

        banner("[14] Pipeline info")
        r = await c.get(f"{BASE}/api/pipelines")
        if r.status_code == 200:
            d = r.json()
            qa.OK("pipelines", f"current.retriever={d.get('current', {}).get('retriever')}")
        else:
            qa.FAIL("pipelines", f"{r.status_code}")

        banner("[15] Chat sessions list")
        r = await c.get(f"{BASE}/api/chat/sessions")
        if r.status_code == 200:
            qa.OK("chat.sessions", f"{len(r.json())} sessions")
        else:
            qa.FAIL("chat.sessions", f"{r.status_code}")

        # Optional: region indexing
        if test_indexing:
            banner("[16] Region indexing (small doc)")
            small = min(completed, key=lambda d: d.get("total_pages") or 999)
            r = await c.post(f"{BASE}/api/lab/region/index/{small['id']}")
            qa.OK("region.index.trigger", str(r.json()))
            for i in range(120):
                await asyncio.sleep(3)
                sr = await c.get(f"{BASE}/api/lab/region/status/{small['id']}", timeout=15)
                st = sr.json()
                if st.get("state") == "completed":
                    qa.OK("region.index.complete", f"indexed={st['indexed']} skipped={st['skipped']} errors={st['errors']}")
                    break
                elif st.get("state") == "failed":
                    qa.FAIL("region.index.failed", st.get("note", ""))
                    break
            else:
                qa.WARN("region.index.timeout", "did not complete in 6 min")

        banner("SUMMARY")
        print(f"  PASS: {len(qa.passes)}")
        print(f"  WARN: {len(qa.warns)}")
        print(f"  FAIL: {len(qa.fails)}")
        if qa.fails:
            print("\n  Failures:")
            for n, d in qa.fails:
                print(f"    - {n}: {d}")
    return qa


if __name__ == "__main__":
    do_idx = "--with-index" in sys.argv
    qa = asyncio.run(main(test_indexing=do_idx))
    sys.exit(1 if qa.fails else 0)
