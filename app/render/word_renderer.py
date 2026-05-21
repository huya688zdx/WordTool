from __future__ import annotations
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from app.config.settings import settings
from app.utils.retry import com_retry

logger = logging.getLogger(__name__)


class WordRenderer:
    """Render DOCX to PDF using Microsoft Word COM automation."""

    def __init__(self, timeout: int = 30, retry_count: int = 3):
        self._word = None
        self._timeout = timeout
        self._retry_count = retry_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False

    def _ensure_word_app(self):
        """Initialize Word COM application instance."""
        if self._word is not None:
            return

        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()
        self._word = win32com.client.DispatchEx("Word.Application")
        self._word.Visible = False
        self._word.DisplayAlerts = False
        # Prevent Word from showing its own password/security dialogs
        try:
            self._word.AutomationSecurity = 1  # msoAutomationSecurityForceDisable
        except Exception:
            pass

    @com_retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
    def render_to_pdf(
        self, docx_path: Path, pdf_path: Path,
        password: str | None = None,
        extract_positions: bool = False,
    ) -> tuple[Path, list[dict] | None]:
        """Render a DOCX/DOC file to PDF using Word COM.

        Args:
            docx_path: Path to the input file (.docx or .doc)
            pdf_path: Path for the output PDF file
            password: Optional password for protected documents
            extract_positions: If True, also extract paragraph positions from Word

        Returns:
            Tuple of (pdf_path, paragraph_positions_or_None)
            Positions list: [{"page": int, "x0": float, "y0": float, "x1": float, "y1": float}, ...]
        """
        self._ensure_word_app()

        docx_str = str(docx_path.resolve())
        pdf_str = str(pdf_path.resolve())

        logger.info(f"Rendering {docx_str} to PDF...")

        doc = None
        positions = None
        try:
            if password:
                doc = self._word.Documents.Open(docx_str, False, True, False, password)
            else:
                doc = self._word.Documents.Open(docx_str)
            doc.ExportAsFixedFormat(
                OutputFileName=pdf_str,
                ExportFormat=17,  # wdExportFormatPDF
                OpenAfterExport=False,
                OptimizeFor=0,  # wdExportOptimizeForPrint
                Range=0,  # wdExportAllDocument
                Item=0,  # wdExportDocumentContent
                IncludeDocProps=True,
                CreateBookmarks=1,  # wdExportCreateWordBookmarks
            )

            if extract_positions:
                positions = self._extract_paragraph_positions(doc)
        finally:
            if doc is not None:
                doc.Close(SaveChanges=False)

        logger.info(f"PDF rendered: {pdf_str}")
        return pdf_path, positions

    def _extract_paragraph_positions(self, doc) -> list[dict]:
        """Extract paragraph positions from an open Word document.

        Uses Word COM Range.Information() to get exact page and position
        for each paragraph. These coordinates match the rendered PDF exactly
        because they come from the same layout engine.
        """
        positions = []
        # Accept all tracked changes temporarily so paragraph count and
        # positions match the PDF (rendered in Final mode). We close
        # without saving so the original file is not modified.
        try:
            doc.Revisions.AcceptAll()
        except Exception:
            pass

        page_setup = doc.PageSetup
        page_w = page_setup.PageWidth
        left_margin = page_setup.LeftMargin
        right_margin = page_setup.RightMargin

        total = doc.Paragraphs.Count
        for i in range(1, total + 1):
            try:
                para = doc.Paragraphs(i)
                rng = para.Range
                # wdActiveEndPageNumber = 3
                page_num = rng.Information(3)

                # Skip empty trailing paragraphs
                text = rng.Text.rstrip("\r\x0b\x07")
                if not text.strip() and i > 1:
                    continue

                # wdVerticalPositionRelativeToPage = 6
                y0 = rng.Information(6)
                # wdHorizontalPositionRelativeToPage = 5
                x0 = rng.Information(5)

                # Use full text column width (page - margins)
                if x0 < left_margin + 2:
                    x0 = left_margin
                x1 = page_w - right_margin

                # Estimate height from next paragraph or use line height
                if i < total:
                    next_rng = doc.Paragraphs(i + 1).Range
                    next_y0 = next_rng.Information(6)
                    if next_y0 > y0:
                        y1 = next_y0 - 2  # small gap
                    else:
                        y1 = y0 + 14  # fallback: ~1 line
                else:
                    y1 = y0 + 14  # last paragraph

                positions.append({
                    "para_index": i - 1,
                    "page": int(page_num),
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                })
            except Exception as e:
                logger.warning(f"Position extraction failed for para {i}: {e}")
                continue

        logger.info(f"Extracted {len(positions)} paragraph positions from Word COM")
        return positions

    def cleanup(self):
        """Quit Word application and release COM reference."""
        if self._word is not None:
            try:
                self._word.Quit()
            except Exception as e:
                logger.warning(f"Error quitting Word: {e}")
            finally:
                self._word = None
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _force_kill_word(self):
        """Force kill Word process if it's stuck."""
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "WINWORD.EXE"],
                capture_output=True,
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Failed to force kill Word: {e}")


def render_docx_to_pdf(
    docx_path: Path, pdf_path: Optional[Path] = None,
    password: str | None = None,
    extract_positions: bool = False,
) -> Path | tuple[Path, list[dict] | None]:
    """Convenience function to render a DOCX/DOC to PDF.

    Args:
        docx_path: Path to the input file
        pdf_path: Optional path for output PDF. If None, uses same name with .pdf extension
        password: Optional password for protected documents
        extract_positions: If True, return (pdf_path, positions_list)

    Returns:
        Path to the generated PDF, or (pdf_path, positions) tuple
    """
    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with WordRenderer(
        timeout=settings.WORD_COM_TIMEOUT_SECONDS,
        retry_count=settings.WORD_COM_RETRY_COUNT,
    ) as renderer:
        result = renderer.render_to_pdf(
            docx_path, pdf_path,
            password=password,
            extract_positions=extract_positions,
        )
        if extract_positions:
            return result  # (pdf_path, positions)
        return result[0]  # pdf_path only
