import os
import pytest
from unittest.mock import patch
from PIL import Image
from backend.strategies.processors.page_screenshot import PageScreenshotProcessor


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path / "images")


@pytest.mark.asyncio
async def test_process_creates_images(tmp_path, output_dir):
    fake_images = [Image.new("RGB", (100, 100), "red"), Image.new("RGB", (100, 100), "blue")]
    with patch("backend.strategies.processors.page_screenshot.convert_from_path", return_value=fake_images):
        processor = PageScreenshotProcessor(images_dir=output_dir)
        pages = await processor.process("/fake/test.pdf", "doc123")
    assert len(pages) == 2
    assert pages[0].document_id == "doc123"
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert os.path.exists(pages[0].image_path)
    assert os.path.exists(pages[1].image_path)
    img = Image.open(pages[0].image_path)
    assert img.size == (100, 100)
