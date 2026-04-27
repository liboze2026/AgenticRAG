from typing import List


class ModelManager:
    def __init__(self, model_name: str = "colpali"):
        self._model_name = model_name
        self._model = None
        self._processor = None

    @staticmethod
    def _colpali_path() -> str:
        import os
        from pathlib import Path
        # Prefer local cache snapshot to avoid HF network calls
        cache_root = Path(os.environ.get("HF_HOME",
                          os.path.expanduser("~/.cache/huggingface"))) / "hub"
        pattern = "models--vidore--colpali-v1.2"
        model_dir = cache_root / pattern / "snapshots"
        if model_dir.exists():
            snapshots = list(model_dir.iterdir())
            if snapshots:
                return str(snapshots[0])
        return "vidore/colpali-v1.2"

    def load(self):
        if self._model_name == "colpali":
            from colpali_engine.models import ColPali, ColPaliProcessor
            path = self._colpali_path()
            self._model = ColPali.from_pretrained(path, device_map="auto").eval()
            self._processor = ColPaliProcessor.from_pretrained(path)

    def encode_images(self, image_paths: List[str], batch_size: int = 2) -> List[dict]:
        from PIL import Image
        images = [Image.open(p).convert("RGB") for p in image_paths]
        return self.encode_images_pil(images, batch_size=batch_size)

    def encode_images_pil(self, images, batch_size: int = 2) -> List[dict]:
        import torch
        all_results = []
        for i in range(0, len(images), batch_size):
            batch = list(images[i:i + batch_size])
            inputs = self._processor.process_images(batch)
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.no_grad():
                embeddings = self._model(**inputs)
            all_results.extend({"vectors": emb.cpu().tolist()} for emb in embeddings)
            del inputs, embeddings
            torch.cuda.empty_cache()
        return all_results

    def encode_query(self, query: str) -> List[List[float]]:
        inputs = self._processor.process_queries([query])
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        with __import__("torch").no_grad():
            embeddings = self._model(**inputs)
        return embeddings[0].cpu().tolist()

    def model_name(self) -> str:
        return self._model_name
