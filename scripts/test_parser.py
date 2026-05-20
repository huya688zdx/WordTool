"""Test script to verify DOCX parsing."""
from pathlib import Path

from app.parser.docx_parser import DocxParser


def test_simple_docx():
    """Test parsing a simple DOCX file."""
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    docx_path = fixtures_dir / "simple.docx"

    parser = DocxParser()
    structure = parser.parse(docx_path)

    print(f"Document metadata: {structure.metadata}")
    print(f"Total paragraphs: {len(structure.paragraphs)}")
    print()

    for para in structure.paragraphs:
        print(f"Para {para.para_index}:")
        print(f"  Style: {para.style_name}")
        print(f"  Heading level: {para.heading_level}")
        print(f"  Text: {para.full_text[:80]}...")
        print(f"  Runs: {len(para.runs)}")
        print(f"  Has highlights: {para.has_highlights}")
        print(f"  Has revisions: {para.has_revisions}")
        print()


def test_highlighted_docx():
    """Test parsing a DOCX with highlights."""
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    docx_path = fixtures_dir / "highlighted.docx"

    parser = DocxParser()
    structure = parser.parse(docx_path)

    print(f"Total paragraphs: {len(structure.paragraphs)}")
    print()

    for para in structure.paragraphs:
        print(f"Para {para.para_index}:")
        print(f"  Text: {para.full_text}")
        print(f"  Has highlights: {para.has_highlights}")
        if para.has_highlights:
            for run in para.runs:
                if run.is_highlighted:
                    print(f"    Highlighted run: '{run.text}' (color: {run.highlight_color})")
        print()


if __name__ == "__main__":
    print("=" * 60)
    print("Testing simple.docx")
    print("=" * 60)
    test_simple_docx()

    print("=" * 60)
    print("Testing highlighted.docx")
    print("=" * 60)
    test_highlighted_docx()
