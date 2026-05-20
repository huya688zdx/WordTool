import logging
from pathlib import Path
from typing import Tuple, Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PageCropper:
    """Crop regions from PDF pages for screenshots."""

    def crop_paragraph(
        self,
        pdf_path: Path,
        page_number: int,
        bbox: Tuple[float, float, float, float],
        padding: float = 10.0,
        zoom: float = 2.0,
    ) -> bytes:
        """Crop a region from a PDF page and return as PNG bytes.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number
            bbox: (x0, y0, x1, y1) bounding box in PDF points
            padding: Padding around the bbox in points
            zoom: Zoom factor for output resolution

        Returns:
            PNG image bytes
        """
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[page_number - 1]
            rect = fitz.Rect(bbox) + (-padding, -padding, padding, padding)

            # Ensure rect is within page bounds
            page_rect = page.rect
            rect = rect & page_rect  # Intersection

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(clip=rect, matrix=mat)
            return pix.tobytes("png")
        finally:
            doc.close()

    def crop_with_context(
        self,
        pdf_path: Path,
        page_number: int,
        bbox: Tuple[float, float, float, float],
        context_lines: int = 2,
        line_height: float = 20.0,
    ) -> bytes:
        """Crop region with extra context above/below."""
        expanded_bbox = (
            bbox[0],
            bbox[1] - (context_lines * line_height),
            bbox[2],
            bbox[3] + (context_lines * line_height),
        )
        return self.crop_paragraph(pdf_path, page_number, expanded_bbox)

    def get_page_thumbnail(
        self,
        pdf_path: Path,
        page_number: int,
        max_width: int = 800,
    ) -> bytes:
        """Generate full page thumbnail for overview display."""
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[page_number - 1]
            page_width = page.rect.width

            # Calculate zoom to fit max_width
            zoom = max_width / page_width if page_width > 0 else 1.0
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat)
            return pix.tobytes("png")
        finally:
            doc.close()

    def get_highlighted_regions(
        self,
        pdf_path: Path,
        page_number: int,
        highlight_color: Tuple[int, int, int] = (1, 1, 0),
    ) -> list:
        """Detect highlighted regions on a page (for PDF-native highlights)."""
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[page_number - 1]
            drawings = page.get_drawings()

            highlights = []
            for d in drawings:
                if d.get("fill"):
                    fill = d["fill"]
                    # Check if fill color matches highlight color (approximate)
                    if (abs(fill[0] - highlight_color[0]) < 0.1 and
                            abs(fill[1] - highlight_color[1]) < 0.1 and
                            abs(fill[2] - highlight_color[2]) < 0.1):
                        highlights.append(d["rect"])

            return highlights
        finally:
            doc.close()


def crop_paragraph_image(
    pdf_path: Path,
    page_number: int,
    bbox: Tuple[float, float, float, float],
    padding: float = 10.0,
    zoom: float = 2.0,
) -> bytes:
    """Convenience function to crop a paragraph from PDF."""
    cropper = PageCropper()
    return cropper.crop_paragraph(pdf_path, page_number, bbox, padding, zoom)
