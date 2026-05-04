import os
from typing import List
from pdf2image import convert_from_path
from backend.interfaces.processor import BaseProcessor
from backend.models.schemas import PageImage
from backend.strategies import processor_registry


@processor_registry.register("page_screenshot")
class PageScreenshotProcessor(BaseProcessor):
    def __init__(self, images_dir: str = "data/images", dpi: int = 200):
        self.images_dir = images_dir
        self.dpi = dpi

    async def process(self, pdf_path: str, document_id: str) -> List[PageImage]:
        doc_dir = os.path.join(self.images_dir, document_id)
        os.makedirs(doc_dir, exist_ok=True)
        try:
            images = convert_from_path(pdf_path, dpi=self.dpi)
        except Exception as e:
            raise RuntimeError(f"PDF 渲染失败 ({type(e).__name__}: {e}) — 文件可能损坏或缺少 poppler") from e
        pages = []
        for i, img in enumerate(images):
            page_num = i + 1
            img_path = os.path.join(doc_dir, f"page_{page_num}.png")
            img.save(img_path, "PNG")
            pages.append(PageImage(document_id=document_id, page_number=page_num, image_path=img_path))
        return pages
