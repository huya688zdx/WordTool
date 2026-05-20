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

    @com_retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
    def render_to_pdf(self, docx_path: Path, pdf_path: Path) -> Path:
        """Render a DOCX file to PDF using Word COM.

        Args:
            docx_path: Path to the input DOCX file
            pdf_path: Path for the output PDF file

        Returns:
            Path to the generated PDF file
        """
        self._ensure_word_app()

        docx_str = str(docx_path.resolve())
        pdf_str = str(pdf_path.resolve())

        logger.info(f"Rendering {docx_str} to PDF...")

        doc = None
        try:
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
        finally:
            if doc is not None:
                doc.Close(SaveChanges=False)

        logger.info(f"PDF rendered: {pdf_str}")
        return pdf_path

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


def render_docx_to_pdf(docx_path: Path, pdf_path: Optional[Path] = None) -> Path:
    """Convenience function to render a DOCX to PDF.

    Args:
        docx_path: Path to the input DOCX file
        pdf_path: Optional path for output PDF. If None, uses same name with .pdf extension

    Returns:
        Path to the generated PDF
    """
    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with WordRenderer(
        timeout=settings.WORD_COM_TIMEOUT_SECONDS,
        retry_count=settings.WORD_COM_RETRY_COUNT,
    ) as renderer:
        return renderer.render_to_pdf(docx_path, pdf_path)
