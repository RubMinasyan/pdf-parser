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


def main():

    pdf_path = "input/Article-4.pdf"

    reader = PDFReader(pdf_path)

    if len(sys.argv) > 1:
        page_range = sys.argv[1]
    else:
        page_range = "all"

    pages = reader.read_pages(page_range)

    raw_text = "\n\n".join(pages)

    cleaner = TextCleaner()
    cleaned_text = cleaner.clean_pages(pages)

    extractor = ArticleExtractor()

    article = extractor.extract(
        cleaned_text,
        reference_text=raw_text
    )

    table_figure_extractor = TableFigureExtractor()

    visual_content = table_figure_extractor.extract(
        pdf_path=pdf_path,
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
    pdf_name = Path(pdf_path).stem

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
    main()
