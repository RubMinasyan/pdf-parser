import fitz  # PyMuPDF
from pathlib import Path


class PDFReader:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)

    def read_pages(self, page_range=None):

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"{self.pdf_path} does not exist.")

        document = fitz.open(self.pdf_path)

        pages = []

        if page_range is None or page_range == "all":
            selected_pages = range(len(document))

        elif isinstance(page_range, str) and "-" in page_range:
            start, end = page_range.split("-")
            selected_pages = range(int(start) - 1, int(end))

        elif page_range.isdigit():
            selected_pages = [int(page_range) - 1]

        else:
            document.close()
            raise ValueError("Use: all, page number, or range like 2-5")

        for page_number in selected_pages:

            if 0 <= page_number < len(document):
                pages.append(document[page_number].get_text())

        document.close()

        return pages
