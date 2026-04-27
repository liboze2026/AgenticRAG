"""Layout-aware PDF processor.

For each page this processor produces a full-page PNG (same as
PageScreenshotProcessor) AND a PageLayout object that describes detected
text blocks, tables, and figures with their bounding boxes.

Coordinate systems
------------------
* pdfplumber uses PDF points with **bottom-left** origin.
* PIL images use pixels with **top-left** origin.

Conversion formula (used in _pdf_bbox_to_px):
    scale = dpi / 72
    x_px  = x_pdf * scale
    y_px  = (page_height_pt - y_pdf_top) * scale   # flip y-axis
"""

import os
from typing import List, Optional, Tuple

from pdf2image import convert_from_path

from backend.interfaces.processor import BaseProcessor
from backend.models.schemas import (
    BoundingBox, LayoutElement, PageImage, PageLayout,
)
from backend.strategies import processor_registry

try:
    import pdfplumber as _pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _pdfplumber = None
    _PDFPLUMBER_OK = False

try:
    import fitz as _fitz          # PyMuPDF
    _FITZ_OK = True
except ImportError:
    _fitz = None
    _FITZ_OK = False


def _pdf_bbox_to_px(
    x0: float, y0: float, x1: float, y1: float,
    page_height_pt: float, scale: float,
) -> Tuple[float, float, float, float]:
    """Convert PDF-point bbox (bottom-left origin) → pixel bbox (top-left origin)."""
    px0 = x0 * scale
    px1 = x1 * scale
    # pdfplumber y0 < y1, both measured from top (unlike raw PDF spec)
    py0 = y0 * scale
    py1 = y1 * scale
    return px0, py0, px1, py1


@processor_registry.register("layout_analysis")
class LayoutAnalysisProcessor(BaseProcessor):
    """Drop-in replacement for PageScreenshotProcessor that also extracts layout."""

    def __init__(
        self,
        images_dir: str = "data/images",
        dpi: int = 200,
        extract_figures: bool = True,
        min_figure_area_pt: float = 2000.0,   # minimum area in PDF-points² to keep
    ):
        self.images_dir = images_dir
        self.dpi = dpi
        self.extract_figures = extract_figures
        self.min_figure_area_pt = min_figure_area_pt
        self._scale = dpi / 72.0

    async def process(self, pdf_path: str, document_id: str) -> List[PageImage]:
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(self._process_sync, pdf_path, document_id)

    def _process_sync(self, pdf_path: str, document_id: str) -> List[PageImage]:
        doc_dir = os.path.join(self.images_dir, document_id)
        os.makedirs(doc_dir, exist_ok=True)

        # Render all pages to PIL images
        pil_images = convert_from_path(pdf_path, dpi=self.dpi)
        pages: List[PageImage] = []

        plumber_pdf = None
        if _PDFPLUMBER_OK:
            try:
                plumber_pdf = _pdfplumber.open(pdf_path)
            except Exception:
                plumber_pdf = None

        for i, pil_img in enumerate(pil_images):
            page_num = i + 1
            img_path = os.path.join(doc_dir, f"page_{page_num}.png")
            pil_img.save(img_path, "PNG")

            layout: Optional[PageLayout] = None
            if plumber_pdf and page_num <= len(plumber_pdf.pages):
                try:
                    layout = self._extract_layout(
                        plumber_pdf.pages[i], document_id, page_num, doc_dir
                    )
                except Exception:
                    layout = None

            pages.append(PageImage(
                document_id=document_id,
                page_number=page_num,
                image_path=img_path,
                layout_metadata=layout,
            ))

        if plumber_pdf:
            try:
                plumber_pdf.close()
            except Exception:
                pass

        return pages

    def _extract_layout(self, plumber_page, document_id: str, page_num: int, doc_dir: str) -> PageLayout:
        pw = float(plumber_page.width)
        ph = float(plumber_page.height)
        elements: List[LayoutElement] = []

        # --- Text blocks ---
        try:
            words = plumber_page.extract_words(x_tolerance=3, y_tolerance=3)
            if words:
                elements.extend(self._group_words_to_blocks(words, document_id, page_num, ph))
        except Exception:
            pass

        # --- Tables ---
        try:
            tables = plumber_page.find_tables()
            for table in tables:
                bbox = table.bbox   # (x0, top, x1, bottom) in PDF points from top
                try:
                    table_text = "\n".join(
                        " | ".join(cell or "" for cell in row)
                        for row in table.extract()
                        if row
                    )
                except Exception:
                    table_text = ""
                elements.append(LayoutElement(
                    element_type="table",
                    bbox=BoundingBox(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]),
                    text=table_text,
                    confidence=1.0,
                ))
        except Exception:
            pass

        # --- Figures (image objects embedded in PDF) ---
        if self.extract_figures:
            elements.extend(
                self._extract_figures(plumber_page, document_id, page_num, doc_dir, ph)
            )

        return PageLayout(
            document_id=document_id,
            page_number=page_num,
            page_width=pw,
            page_height=ph,
            elements=elements,
        )

    def _group_words_to_blocks(
        self, words: list, document_id: str, page_num: int, page_height: float,
    ) -> List[LayoutElement]:
        """Group nearby words into paragraph-level text blocks."""
        if not words:
            return []

        # Sort by top then x0
        words = sorted(words, key=lambda w: (round(w["top"] / 5) * 5, w["x0"]))

        blocks: List[LayoutElement] = []
        current_words = [words[0]]

        for w in words[1:]:
            prev = current_words[-1]
            # Same line or close vertical proximity → same block
            if abs(w["top"] - prev["top"]) < 15:
                current_words.append(w)
            else:
                blocks.append(self._words_to_element(current_words))
                current_words = [w]
        if current_words:
            blocks.append(self._words_to_element(current_words))

        return blocks

    def _words_to_element(self, words: list) -> LayoutElement:
        x0 = min(w["x0"] for w in words)
        y0 = min(w["top"] for w in words)
        x1 = max(w["x1"] for w in words)
        y1 = max(w["bottom"] for w in words)
        text = " ".join(w["text"] for w in words)
        # Heuristic: short all-caps or large-font words → heading
        element_type = "heading" if (y1 - y0 > 16 and len(text) < 120) else "text_block"
        return LayoutElement(
            element_type=element_type,
            bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
            text=text,
        )

    def _extract_figures(
        self, plumber_page, document_id: str, page_num: int, doc_dir: str, page_height: float,
    ) -> List[LayoutElement]:
        """Extract embedded image/figure regions using PyMuPDF if available."""
        if not _FITZ_OK:
            return self._extract_figures_from_rects(plumber_page)

        figures: List[LayoutElement] = []
        try:
            # We use fitz only for image bbox extraction; we get the page via index
            # pdfplumber and fitz may differ in page count handling — use plumber's underlying
            # page index instead
            pdf_path = plumber_page.pdf.stream.name if hasattr(plumber_page.pdf, "stream") else None
            if not pdf_path:
                return self._extract_figures_from_rects(plumber_page)

            fitz_doc = _fitz.open(pdf_path)
            fitz_page = fitz_doc[page_num - 1]
            img_list = fitz_page.get_images(full=True)

            for idx, img_info in enumerate(img_list):
                xref = img_info[0]
                rects = fitz_page.get_image_rects(xref)
                if not rects:
                    continue
                rect = rects[0]
                area = (rect.x1 - rect.x0) * (rect.y1 - rect.y0)
                if area < self.min_figure_area_pt:
                    continue

                # Crop and save the figure
                crop_path = os.path.join(doc_dir, f"page_{page_num}_fig_{idx + 1}.png")
                clip = _fitz.Rect(rect)
                mat = _fitz.Matrix(self._scale, self._scale)
                pix = fitz_page.get_pixmap(matrix=mat, clip=clip)
                pix.save(crop_path)

                # fitz uses top-left origin in PDF points coordinates
                figures.append(LayoutElement(
                    element_type="figure",
                    bbox=BoundingBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1),
                    image_path=crop_path,
                    confidence=1.0,
                ))

            fitz_doc.close()
        except Exception:
            pass

        return figures

    def _extract_figures_from_rects(self, plumber_page) -> List[LayoutElement]:
        """Fallback: detect large rectangles as potential figure regions."""
        figures: List[LayoutElement] = []
        try:
            for rect in plumber_page.rects:
                w = abs(rect["x1"] - rect["x0"])
                h = abs(rect["bottom"] - rect["top"])
                if w * h < self.min_figure_area_pt:
                    continue
                figures.append(LayoutElement(
                    element_type="figure",
                    bbox=BoundingBox(
                        x0=rect["x0"], y0=rect["top"],
                        x1=rect["x1"], y1=rect["bottom"],
                    ),
                    confidence=0.6,
                ))
        except Exception:
            pass
        return figures
