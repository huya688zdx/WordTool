from __future__ import annotations

"""Parse .doc (binary Word 97-2003) files via Word COM automation.

python-docx only handles .docx (Office Open XML). For legacy .doc files,
we use Word COM to extract paragraph structure, styles, and text.
"""

from pathlib import Path

from app.parser.docx_parser import ParagraphData, RunData
from app.utils.xml_helpers import qn, find_child


def parse_doc_via_com(file_path: Path, password: str | None = None) -> list[ParagraphData]:
    """Extract paragraph structure from a .doc file using Word COM.

    Args:
        file_path: Path to the .doc file
        password: Optional document password

    Returns:
        List of ParagraphData with text, style, and heading level info
    """
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    doc = None
    paragraphs = []

    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        try:
            word.AutomationSecurity = 1  # suppress Word password dialogs
        except Exception:
            pass

        file_str = str(file_path.resolve())
        if password:
            doc = word.Documents.Open(file_str, False, True, False, password)
        else:
            doc = word.Documents.Open(file_str)

        total = doc.Paragraphs.Count
        for i in range(1, total + 1):
            para = doc.Paragraphs(i)
            rng = para.Range
            text = rng.Text.rstrip("\r\x0b\x07")  # Word uses \r for paragraph marks

            if not text.strip():
                continue

            # Detect style and heading level
            style_name = None
            heading_level = None
            try:
                style = para.Style
                style_name = style.NameLocal
                if style_name:
                    name_lower = style_name.lower()
                    for prefix in ("heading", "标题"):
                        if name_lower.startswith(prefix):
                            suffix = name_lower[len(prefix):].strip()
                            try:
                                heading_level = int(suffix)
                            except ValueError:
                                pass
                            break
                if heading_level is None:
                    try:
                        ol = para.OutlineLevel
                        if ol and isinstance(ol, int) and ol > 0:
                            heading_level = ol
                    except Exception:
                        pass
            except Exception:
                pass

            has_highlights = False
            has_revisions = False
            try:
                if para.Range.Revisions.Count > 0:
                    has_revisions = True
            except Exception:
                pass

            pdata = ParagraphData(
                para_index=i - 1,
                full_text=text,
                style_name=style_name,
                heading_level=heading_level,
                runs=[RunData(text=text)],
                has_highlights=has_highlights,
                has_revisions=has_revisions,
            )
            paragraphs.append(pdata)

    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    return paragraphs
