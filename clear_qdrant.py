"""Run after backend/SSH tunnel is up: clears all points from documents collection."""
import httpx

r = httpx.post(
    "http://localhost:6333/collections/documents/points/delete",
    json={"filter": {}},
    timeout=60,
)
if r.status_code == 200:
    print("Qdrant documents collection cleared:", r.json())
else:
    print(f"Failed ({r.status_code}):", r.text[:300])
