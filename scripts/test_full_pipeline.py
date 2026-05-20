"""Test the full pipeline: parse -> render -> align."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.parser.docx_parser import DocxParser
from app.render.pdf_parser import PDFParser
from app.render.text_anchor import TextAnchorMapper
from app.render.page_cropper import PageCropper


def test_pipeline():
    """Test the complete pipeline with a simple DOCX."""
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    docx_path = fixtures_dir / "simple.docx"
    pdf_path = fixtures_dir / "simple.pdf"

    # Step 1: Parse DOCX
    print("Step 1: Parsing DOCX...")
    parser = DocxParser()
    structure = parser.parse(docx_path)
    print(f"  Found {len(structure.paragraphs)} paragraphs")

    # Step 2: Check if PDF exists (manual render for now)
    if not pdf_path.exists():
        print(f"\n  PDF not found at {pdf_path}")
        print("  Please render the DOCX to PDF manually using Word:")
        print(f"    1. Open {docx_path} in Word")
        print(f"    2. Save as PDF to {pdf_path}")
        print(f"    3. Run this script again")
        return

    # Step 3: Parse PDF
    print("\nStep 2: Parsing PDF...")
    pdf_parser = PDFParser()
    pages = pdf_parser.parse_document(pdf_path)
    print(f"  Found {len(pages)} pages")
    for page in pages:
        print(f"    Page {page.page_number}: {len(page.blocks)} blocks")

    # Step 4: Map paragraphs to PDF coordinates
    print("\nStep 3: Mapping paragraphs to PDF coordinates...")
    mapper = TextAnchorMapper()
    mappings = mapper.map_paragraphs(structure.paragraphs, str(pdf_path))
    print(f"  Mapped {len(mappings)} paragraphs")

    for mapping in mappings:
        print(f"    Para {mapping.paragraph_id}: page {mapping.page_number}, "
              f"bbox=({mapping.bbox[0]:.1f}, {mapping.bbox[1]:.1f}, "
              f"{mapping.bbox[2]:.1f}, {mapping.bbox[3]:.1f}), "
              f"confidence={mapping.confidence:.2f}, strategy={mapping.strategy}")

    # Step 5: Crop a paragraph
    if mappings:
        print("\nStep 4: Cropping first paragraph...")
        cropper = PageCropper()
        first_mapping = mappings[0]
        image_bytes = cropper.crop_paragraph(
            pdf_path,
            first_mapping.page_number,
            first_mapping.bbox,
        )
        print(f"  Cropped image size: {len(image_bytes)} bytes")

    print("\nPipeline test completed successfully!")


if __name__ == "__main__":
    test_pipeline()
