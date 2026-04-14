from typing import List


class ModelManager:
    def __init__(self, model_name: str = "colpali"):
        self._model_name = model_name
        self._model = None
        self._processor = None

    def load(self):
        if self._model_name == "colpali":
            from colpali_engine.models import ColPali, ColPaliProcessor
            self._model = ColPali.from_pretrained("vidore/colpali-v1.2", device_map="auto").eval()
            self._processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")

    def encode_images(self, image_paths: List[str], batch_size: int = 2) -> List[dict]:
        import torch
        from PIL import Image

        all_results = []
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            images = [Image.open(p).convert("RGB") for p in batch_paths]
            inputs = self._processor.process_images(images)
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.no_grad():
                embeddings = self._model(**inputs)
            all_results.extend({"vectors": emb.cpu().tolist()} for emb in embeddings)
            # Free GPU memory between batches
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
