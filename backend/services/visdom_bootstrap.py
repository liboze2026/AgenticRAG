"""On-startup VisDoM SPIQA bootstrap.

If enabled and the Qdrant collection is empty, pulls the top-N most-queried
SPIQA papers from the active SSH server via SFTP and runs them through the
normal document_service.upload + index_document path. Failures are logged
and swallowed — bootstrap should never prevent the API from serving.
"""
import asyncio
import collections
import csv
import io
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def _open_sftp(active_srv: dict, ssh_connect_fn):
    """Open an SFTP session against the active SSH server.

    ssh_connect_fn is injected to avoid pulling run.py into this module.
    """
    bastion, target = ssh_connect_fn(active_srv)
    sftp = target.open_sftp()
    return sftp, target, bastion


def _pick_top_papers(csv_text: str, top_n: int) -> List[str]:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    counts = collections.Counter(r["doc_id"] for r in rows if r.get("doc_id"))
    return [doc for doc, _ in counts.most_common(top_n)]


async def bootstrap_visdom_if_empty(
    active_srv: dict,
    ssh_connect_fn,
    document_service,
    qdrant_client,
    collection_name: str,
    top_n: int = 3,
) -> None:
    """Run the bootstrap if it's safe to do so. Logs and returns on any error."""
    if not active_srv:
        logger.info("[bootstrap-visdom] no active SSH server, skip")
        return

    deploy = active_srv.get("deployment", {}) or {}
    visdom_remote = deploy.get("visdom_data")
    if not visdom_remote:
        logger.info("[bootstrap-visdom] no visdom_data path on active server, skip")
        return

    # 1. Confirm collection is genuinely empty (don't clobber existing data)
    try:
        info = await qdrant_client.get_collection(collection_name)
        existing = getattr(info, "points_count", None)
        if existing is None:
            existing = getattr(info, "vectors_count", 0) or 0
        if existing > 0:
            logger.info("[bootstrap-visdom] collection has %d points, skip", existing)
            return
    except Exception as e:
        logger.warning("[bootstrap-visdom] could not inspect collection: %s — skip", e)
        return

    # 2. Pull spiqa.csv via SFTP, pick top-N papers
    try:
        sftp, target, bastion = await asyncio.to_thread(
            _open_sftp, active_srv, ssh_connect_fn
        )
    except Exception as e:
        logger.warning("[bootstrap-visdom] SFTP open failed: %s — skip", e)
        return

    try:
        csv_remote = f"{visdom_remote}/spiqa/spiqa.csv"
        try:
            with sftp.open(csv_remote) as f:
                csv_text = f.read().decode("utf-8", errors="replace")
        except IOError as e:
            logger.warning("[bootstrap-visdom] could not read %s: %s", csv_remote, e)
            return

        top = _pick_top_papers(csv_text, top_n)
        logger.info("[bootstrap-visdom] picked top %d: %s", len(top), top)

        # 3. For each PDF: SFTP it down, register, kick off indexing
        for doc_id in top:
            remote_pdf = f"{visdom_remote}/spiqa/docs/{doc_id}.pdf"
            tmp_path = os.path.join(document_service.upload_dir, f"_visdom_{doc_id}.pdf")
            try:
                await asyncio.to_thread(sftp.get, remote_pdf, tmp_path)
            except IOError as e:
                logger.warning("[bootstrap-visdom] SFTP get %s failed: %s", remote_pdf, e)
                continue

            with open(tmp_path, "rb") as f:
                content = f.read()
            os.unlink(tmp_path)

            try:
                doc_info = await document_service.upload(
                    filename=f"{doc_id}.pdf", content=content, dataset_id=None,
                )
                # Fire-and-forget indexing
                asyncio.create_task(
                    document_service.index_document(doc_info.id),
                    name=f"bootstrap-index-{doc_info.id}",
                )
                logger.info("[bootstrap-visdom] queued %s -> %s", doc_id, doc_info.id)
            except Exception as e:
                logger.warning("[bootstrap-visdom] register/index %s failed: %s", doc_id, e)

    finally:
        try: sftp.close()
        except Exception: pass
        try: target.close()
        except Exception: pass
        if bastion is not None:
            try: bastion.close()
            except Exception: pass
