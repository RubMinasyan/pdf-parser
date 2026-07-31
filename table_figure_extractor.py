import re
from typing import Any

import pdfplumber


class TableFigureExtractor:

    TABLE_TITLE_PATTERN = re.compile(
        r"^Table\s+(\d+)\s*[-:–—]\s*(.+)$",
        re.IGNORECASE
    )

    FIGURE_PATTERN = re.compile(
        r"^(?:Figure|Fig\.?)\s+(\d+)\s*[-:–—]?\s*(.*)$",
        re.IGNORECASE | re.MULTILINE
    )

    CELL_REPLACEMENTS = {
        "\ue081": "(",
        "\ue082": ")",
        "\ue083": "[",
        "\ue084": "]",
        "\ue088": "–",
        "\ue089": "–",
        "\ue09b": " = ",
        "￾": "",
    }

    OUTPUT_HEADERS = [
        "study_name",
        "year_last_reported",
        "regimen",
        "number_of_patients",
        "response_rate_percent",
        "median_survival_months_95_ci",
    ]

    def extract(self, pdf_path: str, page_range: str = "all") -> dict:
        tables = []
        figures = []

        with pdfplumber.open(pdf_path) as pdf:
            page_numbers = self._parse_page_range(
                page_range,
                total_pages=len(pdf.pages)
            )

            for page_number in page_numbers:
                page = pdf.pages[page_number - 1]

                for extracted_table in page.extract_tables():
                    structured_table = self._structure_table(
                        extracted_table,
                        page_number
                    )

                    if structured_table:
                        tables.append(structured_table)

                page_text = page.extract_text() or ""
                figures.extend(
                    self._extract_figures_from_page(
                        page_text,
                        page_number
                    )
                )

        tables.sort(
            key=lambda table: (table["page"], table["number"])
        )
        figures.sort(
            key=lambda figure: (figure["page"], figure["number"])
        )

        return {
            "tables": tables,
            "figures": figures
        }

    def remove_table_blocks(
        self,
        article_text: str,
        tables: list[dict]
    ) -> str:
        """Remove raw table text already stored as structured data."""
        if not article_text or not tables:
            return article_text

        cleaned_text = article_text

        for table in tables:
            table_number = table["number"]

            table_start_pattern = re.compile(
                rf"^Table\s+{table_number}\s*[-:–—].*$",
                re.IGNORECASE | re.MULTILINE
            )

            start_match = table_start_pattern.search(cleaned_text)
            if not start_match:
                continue

            table_end_pattern = re.compile(
                r"^NR\s*(?:=|[-:])?\s*Not reached\s*$",
                re.IGNORECASE | re.MULTILINE
            )

            end_match = table_end_pattern.search(
                cleaned_text,
                start_match.end()
            )

            if not end_match:
                continue

            removal_end = end_match.end()

            # Consume citation fragments placed below the table, such as:
            # [37 38], [39 40], [41 42] or [24,25], [26], [27], 28].
            citation_lines_pattern = re.compile(
                r"(?:\n[ \t]*\[?\d+(?:[ \t]*[, ]+[ \t]*\d+)*\]?[ \t]*)*"
            )
            citation_match = citation_lines_pattern.match(
                cleaned_text,
                removal_end
            )

            if citation_match:
                removal_end = citation_match.end()

            cleaned_text = (
                cleaned_text[:start_match.start()].rstrip()
                + "\n"
                + cleaned_text[removal_end:].lstrip()
            )

        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def _structure_table(
        self,
        extracted_table: list[list[Any]],
        page_number: int
    ) -> dict | None:
        if len(extracted_table) < 3:
            return None

        title = self._clean_cell(extracted_table[0][0])
        title_match = self.TABLE_TITLE_PATTERN.match(title)

        if not title_match:
            return None

        table_number = int(title_match.group(1))
        table_title = title_match.group(2).strip()

        source_headers = [
            self._clean_cell(cell)
            for cell in extracted_table[1]
        ]

        rows = []
        notes = []
        current_study = ""
        current_year = ""

        for source_row in extracted_table[2:]:
            cells = [self._clean_cell(cell) for cell in source_row]
            cells += [""] * (6 - len(cells))
            cells = cells[:6]

            if not any(cells):
                continue

            if self._is_note_row(cells):
                note = next((cell for cell in cells if cell), "")
                if note:
                    notes.append(note)
                continue

            study_name, year, regimen, patients, response, survival = cells

            if study_name:
                current_study = study_name
            if year:
                current_year = year

            rows.append({
                "study_name": current_study or None,
                "year_last_reported": current_year or None,
                "regimen": regimen or None,
                "number_of_patients": self._to_int_or_none(patients),
                "response_rate_percent": self._to_number_or_none(response),
                "median_survival_months_95_ci": survival or None,
            })

        return {
            "id": f"Table {table_number}",
            "number": table_number,
            "title": table_title,
            "page": page_number,
            "source_headers": source_headers,
            "headers": self.OUTPUT_HEADERS.copy(),
            "rows": rows,
            "notes": notes,
        }

    def _extract_figures_from_page(
        self,
        page_text: str,
        page_number: int
    ) -> list[dict]:
        figures = []

        for match in self.FIGURE_PATTERN.finditer(page_text):
            figures.append({
                "id": f"Figure {int(match.group(1))}",
                "number": int(match.group(1)),
                "title": self._clean_cell(match.group(2)),
                "page": page_number,
                "caption": ""
            })

        return figures

    def _clean_cell(self, value: Any) -> str:
        if value is None:
            return ""

        text = str(value)

        for old, new in self.CELL_REPLACEMENTS.items():
            text = text.replace(old, new)

        text = re.sub(r"-\n(?=[a-z])", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*=\s*", " = ", text)

        return text

    def _is_note_row(self, cells: list[str]) -> bool:
        nonempty = [cell for cell in cells if cell]

        return (
            len(nonempty) == 1
            and bool(re.fullmatch(
                r"NR\s*=\s*Not reached",
                nonempty[0],
                re.IGNORECASE
            ))
        )

    def _to_int_or_none(self, value: str) -> int | None:
        if re.fullmatch(r"\d+", value):
            return int(value)
        return None

    def _to_number_or_none(self, value: str) -> int | float | None:
        if re.fullmatch(r"\d+", value):
            return int(value)

        if re.fullmatch(r"\d+\.\d+", value):
            return float(value)

        return None

    def _parse_page_range(
        self,
        page_range: str,
        total_pages: int
    ) -> list[int]:
        page_range = page_range.strip().lower()

        if page_range == "all":
            return list(range(1, total_pages + 1))

        if re.fullmatch(r"\d+", page_range):
            page_number = int(page_range)
            self._validate_page_number(page_number, total_pages)
            return [page_number]

        match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", page_range)

        if not match:
            raise ValueError(
                "Page range must be 'all', a page number, "
                "or a range such as '4-6'."
            )

        start_page = int(match.group(1))
        end_page = int(match.group(2))

        self._validate_page_number(start_page, total_pages)
        self._validate_page_number(end_page, total_pages)

        if start_page > end_page:
            raise ValueError(
                "The first page cannot be greater than the last page."
            )

        return list(range(start_page, end_page + 1))

    def _validate_page_number(
        self,
        page_number: int,
        total_pages: int
    ) -> None:
        if page_number < 1 or page_number > total_pages:
            raise ValueError(
                f"Page {page_number} is outside the PDF range "
                f"1-{total_pages}."
            )
