"""End-to-end smoke test: hit every API endpoint and report status.

Used during QA to surface bugs without driving the UI. Treats 4xx for
empty queries / missing docs as expected, only flags 5xx + network errors
as failures.
"""
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Tuple

# Ensure local requests bypass any system / mihomo proxy before importing httpx.
for _v in ("NO_PROXY", "no_proxy"):
    os.environ[_v] = (os.environ.get(_v, "") + ",localhost,127.0.0.1").lstrip(",")
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""

import httpx

BASE = "http://127.0.0.1:8080"


class QAResult:
    def __init__(self):
        self.passes: List[str] = []
        self.warns: List[Tuple[str, str]] = []
        self.fails: List[Tuple[str, str]] = []

    def passing(self, name: str):
        self.passes.append(name)
        print(f"  [PASS] {name}")

    def warn(self, name: str, msg: str):
        self.warns.append((name, msg))
        print(f"  [WARN] {name} — {msg}")

    def fail(self, name: str, msg: str):
        self.fails.append((name, msg))
        print(f"  [FAIL] {name} — {msg}")


async def hit(client: httpx.AsyncClient, method: str, path: str,
              expect: int = 200, **kwargs) -> Tuple[int, Any]:
    try:
        r = await client.request(method, BASE + path, timeout=60, **kwargs)
        try:
            body = r.json()
        except Exception:
            body = r.text[:200]
        return r.status_code, body
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


async def main():
    res = QAResult()
    # mounts={"all://": httpx.AsyncHTTPTransport(proxy=None)} forces no proxy
    async with httpx.AsyncClient(trust_env=False) as c:
        # ----- Phase: meta -----
        print("\n[1] Meta endpoints")
        sc, body = await hit(c, "GET", "/api/health")
        if sc == 200:
            res.passing(f"/api/health -> {body}")
        else:
            res.fail("/api/health", f"status={sc} body={body}")

        sc, body = await hit(c, "GET", "/api/lab/info")
        if sc == 200 and body.get("phases"):
            res.passing(f"/api/lab/info -> {len(body['phases'])} phases")
        else:
            res.fail("/api/lab/info", f"status={sc}")

        sc, body = await hit(c, "GET", "/api/lab/health")
        if sc == 200:
            res.passing(f"/api/lab/health -> main_ok={body.get('main_pipeline_ok')} layout_ready={body.get('layout_ready')}")
        else:
            res.fail("/api/lab/health", f"status={sc} body={body}")

        # ----- Phase: documents -----
        print("\n[2] Documents")
        sc, body = await hit(c, "GET", "/api/documents")
        if sc == 200:
            docs = body if isinstance(body, list) else []
            completed = [d for d in docs if d.get("status") == "completed"]
            res.passing(f"/api/documents -> {len(docs)} total, {len(completed)} completed")
        else:
            res.fail("/api/documents", f"status={sc}")
            completed = []

        # ----- Phase: input validation -----
        print("\n[3] Validation (empty / oversize)")
        for path in ["/api/query", "/api/retrieve", "/api/lab/hybrid",
                     "/api/lab/visa", "/api/lab/gmm", "/api/lab/region/query"]:
            sc, body = await hit(c, "POST", path, json={"query": "", "top_k": 5})
            if sc == 400:
                res.passing(f"{path} rejects empty query (400)")
            elif sc == 422:
                res.passing(f"{path} rejects empty query (422)")
            else:
                res.warn(f"{path} empty query", f"got {sc}, expected 400/422")

        # ----- Phase: real query (only if completed docs) -----
        print("\n[4] Real query (requires indexed docs)")
        if not completed:
            res.warn("real query suite", "no completed documents — skipping")
        else:
            test_query = "什么是 ColPali"
            for path, name in [
                ("/api/retrieve", "retrieve"),
                ("/api/lab/hybrid", "hybrid"),
                ("/api/lab/gmm", "gmm"),
                ("/api/lab/region/query", "region"),
            ]:
                sc, body = await hit(c, "POST", path, json={"query": test_query, "top_k": 3})
                if sc == 200:
                    res.passing(f"POST {path} OK ({name})")
                elif sc == 503:
                    res.warn(f"POST {path}", f"503 — {body.get('detail') if isinstance(body, dict) else body}")
                else:
                    res.fail(f"POST {path}", f"status={sc} body={body}")

            # VISA/query/visa includes generation — slower
            for path, name in [("/api/query", "query"), ("/api/lab/visa", "visa")]:
                sc, body = await hit(c, "POST", path, json={"query": test_query, "top_k": 3})
                if sc == 200:
                    res.passing(f"POST {path} OK ({name})")
                elif sc == 503:
                    res.warn(f"POST {path}", f"503 — {body.get('detail') if isinstance(body, dict) else body}")
                else:
                    res.fail(f"POST {path}", f"status={sc} body={body}")

        # ----- Phase: image fetch + missing -----
        print("\n[5] Image serving")
        sc, body = await hit(c, "GET", "/api/images/nonexistent/page_1.png")
        if sc == 200:
            res.passing("/api/images/* placeholder fallback")
        else:
            res.fail("/api/images placeholder", f"status={sc}")

        # ----- Summary -----
        print("\n=== SUMMARY ===")
        print(f"  PASS: {len(res.passes)}")
        print(f"  WARN: {len(res.warns)}")
        print(f"  FAIL: {len(res.fails)}")
        if res.fails:
            print("\nFAILURES:")
            for n, m in res.fails:
                print(f"  {n}: {m}")
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
