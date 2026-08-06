from article_extractor import ArticleExtractor
from pdf_reader import PDFReader
from text_cleaner import TextCleaner
from section_extractor import SectionExtractor
from table_figure_extractor import TableFigureExtractor
from json_writer import JSONWriter
from validator import ArticleValidator

from pathlib import Path
import sys
import json


def get_pdf_path() -> Path:

    input_directory = Path("input")

    if len(sys.argv) > 1:
        pdf_filename = sys.argv[1].strip()
    else:
        pdf_filename = input(
            "Enter the exact PDF filename from input/ "
            "(example: RMS.pdf): "
        ).strip()

    if not pdf_filename:
        raise ValueError("PDF filename cannot be empty.")

    # Accept only a filename located inside input/.
    # Correct example: RMS.pdf
    # Incorrect example: input/RMS.pdf
    if Path(pdf_filename).name != pdf_filename:
        raise ValueError(
            "Enter only the PDF filename, not a full path. "
            "Example: RMS.pdf"
        )

    if Path(pdf_filename).suffix.lower() != ".pdf":
        raise ValueError(
            "The input filename must end with .pdf"
        )

    pdf_path = input_directory / pdf_filename

    if not pdf_path.is_file():

        available_pdfs = sorted(
            path.name
            for path in input_directory.glob("*.pdf")
            if path.is_file()
        )

        if available_pdfs:
            available_text = "\n".join(
                f"  - {filename}"
                for filename in available_pdfs
            )

            raise FileNotFoundError(
                f"{pdf_path} does not exist.\n"
                f"Available PDF files:\n{available_text}"
            )

        raise FileNotFoundError(
            f"{pdf_path} does not exist. "
            "No PDF files were found inside input/."
        )

    return pdf_path


def get_page_range() -> str:

    # Examples:
    # python main.py RMS.pdf
    # python main.py RMS.pdf all
    # python main.py RMS.pdf 3
    # python main.py RMS.pdf 2-5
    if len(sys.argv) > 2:
        return sys.argv[2].strip()

    return "all"


def main():

    if len(sys.argv) > 3:
        raise ValueError(
            "Usage: python main.py "
            "[filename.pdf] [all|page|start-end]"
        )

    pdf_path = get_pdf_path()
    page_range = get_page_range()

    print(f"Input PDF: {pdf_path}")
    print(f"Page range: {page_range}")

    reader = PDFReader(str(pdf_path))

    pages = reader.read_pages(page_range)

    raw_text = "\n\n".join(pages)

    cleaner = TextCleaner()
    cleaned_text = cleaner.clean_pages(pages)

    extractor = ArticleExtractor()

    article = extractor.extract(
        cleaned_text,
        reference_text=raw_text,
        pdf_path=str(pdf_path)
    )

    table_figure_extractor = TableFigureExtractor()

    visual_content = table_figure_extractor.extract(
        pdf_path=str(pdf_path),
        page_range=page_range
    )

    # Remove raw table blocks before section detection.
    article["article_text"] = (
        table_figure_extractor.remove_table_blocks(
            article_text=article["article_text"],
            tables=visual_content["tables"]
        )
    )

    section_extractor = SectionExtractor()

    article["sections"] = section_extractor.extract_sections(
        article["article_text"]
    )

    article["tables"] = visual_content["tables"]
    article["figures"] = visual_content["figures"]

    # Validate the complete result.
    validator = ArticleValidator()

    validation = validator.validate(
        article,
        require_complete=(page_range == "all")
    )

    # Build output filenames.
    pdf_name = pdf_path.stem

    json_output_path = Path(
        "output",
        f"{pdf_name}.json"
    )

    validation_output_path = Path(
        "output",
        f"{pdf_name}_validation.json"
    )

    # Save the article and validation report.
    writer = JSONWriter()

    saved_json_path = writer.save(
        article,
        json_output_path
    )

    saved_validation_path = writer.save(
        validation,
        validation_output_path
    )

    print(
        json.dumps(
            article,
            indent=4,
            ensure_ascii=False
        )
    )

    print(f"Pages extracted: {len(pages)}")
    print(f"JSON saved: {saved_json_path}")
    print(
        f"Validation report saved: "
        f"{saved_validation_path}"
    )

    if validation["valid"]:
        print("Validation: PASSED")
    else:
        print("Validation: FAILED")

    for error in validation["errors"]:
        print(f"ERROR: {error}")

    for warning in validation["warnings"]:
        print(f"WARNING: {warning}")


if __name__ == "__main__":

    try:
        main()

    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
