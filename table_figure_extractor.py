import re
from statistics import median
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

    ARTICLE_HEADERS = [
        "study_name",
        "year_last_reported",
        "regimen",
        "number_of_patients",
        "response_rate_percent",
        "median_survival_months_95_ci",
    ]

    def __init__(self):
        self._generic_removal_fragments = []

    def extract(self, pdf_path: str, page_range: str = "all") -> dict:
        tables = []
        figures = []
        generic_fragments = []

        self._generic_removal_fragments = []

        with pdfplumber.open(pdf_path) as pdf:
            page_numbers = self._parse_page_range(
                page_range,
                total_pages=len(pdf.pages)
            )

            for page_number in page_numbers:
                original_page = pdf.pages[page_number - 1]
                clean_page = original_page.dedupe_chars(tolerance=1)

                page_has_article_table = False

                for extracted_table in original_page.extract_tables():
                    structured_table = self._structure_article_table(
                        extracted_table,
                        page_number
                    )

                    if structured_table:
                        tables.append(structured_table)
                        page_has_article_table = True

                # The old article tables already contain a caption in their
                # first row. Generic extraction is only needed when that
                # format was not found on the page.
                if not page_has_article_table:
                    regions = self._find_ruled_table_regions(original_page)

                    for region in regions:
                        fragment = self._extract_generic_fragment(
                            clean_page=clean_page,
                            original_page=original_page,
                            region=region,
                            page_number=page_number
                        )

                        if fragment:
                            generic_fragments.append(fragment)

                figures.extend(
                    self._extract_figures_from_page(
                        original_page,
                        page_number
                    )
                )

        generic_tables = self._assemble_generic_tables(
            generic_fragments,
            existing_numbers={table["number"] for table in tables}
        )

        tables.extend(generic_tables)

        tables.sort(
            key=lambda table: (
                table.get("page", 0),
                table.get("number", 0)
            )
        )

        figures.sort(
            key=lambda figure: (
                figure["page"],
                figure["number"]
            )
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

        # Preserve the original Article-4 removal logic.
        for table in tables:
            if "page_end" in table:
                continue

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

        # Generic tables can have captions below the table and can continue
        # onto another page. Remove each extracted fragment separately using
        # its first and last row labels, rather than deleting everything up
        # to the final caption.
        for fragment in self._generic_removal_fragments:
            cleaned_text = self._remove_generic_fragment(
                cleaned_text,
                fragment
            )

        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def _structure_article_table(
        self,
        extracted_table: list[list[Any]],
        page_number: int
    ) -> dict | None:
        """Keep the tested six-column format used by Article-4."""
        if len(extracted_table) < 3:
            return None

        first_row = extracted_table[0]
        if not first_row:
            return None

        title = self._clean_cell(first_row[0])
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
            "headers": self.ARTICLE_HEADERS.copy(),
            "rows": rows,
            "notes": notes,
        }

    def _find_ruled_table_regions(self, page) -> list[dict]:
        """Find table areas from repeated horizontal rules."""
        horizontal_edges = [
            edge
            for edge in page.edges
            if edge.get("orientation") == "h"
            and edge.get("width", 0) >= 120
            and 20 < edge.get("top", 0) < page.height - 20
        ]

        if not horizontal_edges:
            return []

        clusters = {}

        for edge in horizontal_edges:
            # Tables on these PDFs keep an almost constant left edge even
            # when some rows are slightly wider than others.
            key = round(edge["x0"] / 10) * 10
            clusters.setdefault(key, []).append(edge)

        regions = []

        for edges in clusters.values():
            y_values = self._merge_close_values(
                [edge["top"] for edge in edges],
                tolerance=2.5
            )

            if len(y_values) < 4:
                continue

            x0 = min(edge["x0"] for edge in edges)
            x1 = max(edge["x1"] for edge in edges)
            top = max(0, min(y_values))
            bottom = min(page.height, max(y_values))

            if bottom - top < 50:
                continue

            regions.append({
                "x0": x0,
                "x1": x1,
                "top": top,
                "bottom": bottom,
                "row_boundaries": y_values,
            })

        regions.sort(key=lambda item: (item["top"], item["x0"]))
        return regions

    def _extract_generic_fragment(
        self,
        clean_page,
        original_page,
        region: dict,
        page_number: int
    ) -> dict | None:
        bbox = (
            region["x0"],
            region["top"],
            region["x1"],
            region["bottom"]
        )

        crop = clean_page.crop(bbox, strict=False)
        words = crop.extract_words(
            use_text_flow=False,
            keep_blank_chars=False
        )

        if not words:
            return None

        numeric_anchors = self._infer_numeric_anchors(
            words,
            region_x0=region["x0"]
        )

        if not numeric_anchors:
            return None

        row_cells = []
        boundaries = region["row_boundaries"]

        for index in range(len(boundaries) - 1):
            row_top = boundaries[index]
            row_bottom = boundaries[index + 1]

            row_words = [
                word
                for word in words
                if row_top <= self._word_center_y(word) < row_bottom
            ]

            if not row_words:
                continue

            cells = self._words_to_cells(
                row_words,
                numeric_anchors,
                allow_text_columns=(index == 0)
            )

            if any(cells):
                row_cells.append(cells)

        if len(row_cells) < 2:
            return None

        headers = None
        data_rows = row_cells

        if self._looks_like_header(row_cells[0]):
            headers = self._normalize_headers(row_cells[0])
            data_rows = row_cells[1:]

        if headers is None:
            headers = [
                "label",
                *[
                    f"value_{index}"
                    for index in range(1, len(numeric_anchors) + 1)
                ]
            ]

        headers = self._make_unique_headers(headers)

        rows = []

        for cells in data_rows:
            cells += [""] * (len(headers) - len(cells))
            cells = cells[:len(headers)]

            rows.append({
                header: self._convert_generic_value(value)
                for header, value in zip(headers, cells)
            })

        caption = self._find_caption_below_region(
            original_page,
            region
        )

        first_label = self._first_meaningful_label(row_cells)
        last_label = self._last_meaningful_label(row_cells)

        removal_fragment = {
            "page": page_number,
            "first_label": first_label,
            "last_label": last_label,
            "header_cells": row_cells[0] if self._looks_like_header(row_cells[0]) else [],
            "last_cells": row_cells[-1],
        }

        return {
            "page": page_number,
            "headers": headers,
            "rows": rows,
            "caption": caption,
            "removal_fragment": removal_fragment,
        }

    def _assemble_generic_tables(
        self,
        fragments: list[dict],
        existing_numbers: set[int]
    ) -> list[dict]:
        if not fragments:
            return []

        tables = []
        pending = None
        used_numbers = set(existing_numbers)

        for fragment in fragments:
            caption = fragment.get("caption")

            if pending is None:
                pending = fragment
            elif (
                not pending.get("caption")
                and self._fragments_are_compatible(pending, fragment)
                and fragment["page"] == pending["page_end"] + 1
            ):
                remapped_rows = []

                for row in fragment["rows"]:
                    values = list(row.values())
                    values += [None] * (len(pending["headers"]) - len(values))

                    remapped_rows.append({
                        header: values[index]
                        for index, header in enumerate(pending["headers"])
                    })

                pending["rows"].extend(remapped_rows)
                pending["page_end"] = fragment["page"]
                pending["removal_fragments"].append(
                    fragment["removal_fragment"]
                )

                if caption:
                    pending["caption"] = caption
            else:
                tables.append(
                    self._finalize_generic_table(
                        pending,
                        used_numbers
                    )
                )
                pending = fragment

            if "page_end" not in pending:
                pending["page_end"] = pending["page"]

            if "removal_fragments" not in pending:
                pending["removal_fragments"] = [
                    pending["removal_fragment"]
                ]

            # A caption means this table is complete on the current page.
            if pending.get("caption"):
                tables.append(
                    self._finalize_generic_table(
                        pending,
                        used_numbers
                    )
                )
                pending = None

        if pending is not None:
            tables.append(
                self._finalize_generic_table(
                    pending,
                    used_numbers
                )
            )

        return tables

    def _finalize_generic_table(
        self,
        fragment: dict,
        used_numbers: set[int]
    ) -> dict:
        caption = fragment.get("caption") or {}
        source_number = caption.get("number")

        if source_number and source_number not in used_numbers:
            table_number = source_number
        else:
            table_number = 1
            while table_number in used_numbers:
                table_number += 1

        used_numbers.add(table_number)

        title = caption.get("title") or f"Untitled table on page {fragment['page']}"
        notes = []

        if source_number and source_number != table_number:
            notes.append(
                f"Source caption says Table {source_number}; "
                f"assigned Table {table_number} to keep IDs unique."
            )

        self._generic_removal_fragments.extend(
            fragment.get("removal_fragments", [])
        )

        table = {
            "id": f"Table {table_number}",
            "number": table_number,
            "title": title,
            "page": fragment["page"],
            "page_end": fragment.get("page_end", fragment["page"]),
            "source_headers": fragment["headers"],
            "headers": fragment["headers"],
            "rows": fragment["rows"],
            "notes": notes,
        }

        if source_number is not None:
            table["source_number"] = source_number

        return table

    def _fragments_are_compatible(
        self,
        first: dict,
        second: dict
    ) -> bool:
        if len(first["headers"]) != len(second["headers"]):
            return False

        # Continuation pages often repeat no header at all. The number of
        # columns is therefore the safest compatibility check here.
        return True

    def _find_caption_below_region(
        self,
        page,
        region: dict
    ) -> dict | None:
        top = max(0, region["bottom"] - 3)
        bottom = min(page.height, region["bottom"] + 75)

        if bottom <= top:
            return None

        caption_crop = page.crop(
            (
                max(0, region["x0"] - 2),
                top,
                min(page.width, region["x1"] + 2),
                bottom
            ),
            strict=False
        )

        lines = [
            self._clean_cell(line)
            for line in (caption_crop.extract_text() or "").splitlines()
            if self._clean_cell(line)
        ]

        for index, line in enumerate(lines):
            match = self.TABLE_TITLE_PATTERN.match(line)

            if not match:
                continue

            title = match.group(2).strip()

            if index + 1 < len(lines):
                continuation = lines[index + 1]

                if (
                    continuation
                    and continuation[0].islower()
                    and not re.fullmatch(r"\d+", continuation)
                ):
                    title = f"{title} {continuation}"

            return {
                "number": int(match.group(1)),
                "title": title,
            }

        return None

    def _infer_numeric_anchors(
        self,
        words: list[dict],
        region_x0: float
    ) -> list[float]:
        numeric_x_values = []

        for word in words:
            token = self._clean_cell(word.get("text", ""))

            if self._is_numeric_token(token):
                numeric_x_values.append(float(word["x0"]))

        if len(numeric_x_values) < 2:
            return []

        numeric_x_values.sort()
        clusters = []

        for value in numeric_x_values:
            if not clusters or value - clusters[-1][-1] > 25:
                clusters.append([value])
            else:
                clusters[-1].append(value)

        anchors = [
            median(cluster)
            for cluster in clusters
            if len(cluster) >= 2
        ]

        # Numeric-looking labels such as <1, Stage 1, N0, and CG I
        # can form a false cluster inside the first text column.
        if (
            len(anchors) >= 3
            and anchors[0] - region_x0 < 50
            and anchors[1] - anchors[0] > 40
        ):
            anchors = anchors[1:]

        return anchors

    def _words_to_cells(
        self,
        row_words: list[dict],
        numeric_anchors: list[float],
        allow_text_columns: bool = False
    ) -> list[str]:
        cell_words = [[] for _ in range(len(numeric_anchors) + 1)]

        for word in sorted(
            row_words,
            key=lambda item: (item["top"], item["x0"])
        ):
            token = self._clean_cell(word.get("text", ""))

            if not token:
                continue

            if self._is_numeric_token(token):
                nearest_index = min(
                    range(len(numeric_anchors)),
                    key=lambda index: abs(
                        float(word["x0"]) - numeric_anchors[index]
                    )
                )

                if abs(float(word["x0"]) - numeric_anchors[nearest_index]) <= 45:
                    cell_words[nearest_index + 1].append(word)
                else:
                    cell_words[0].append(word)
            else:
                if not allow_text_columns:
                    cell_words[0].append(word)
                    continue

                # Header words are positioned over their numeric columns.
                nearest_index = min(
                    range(len(numeric_anchors)),
                    key=lambda index: abs(
                        float(word["x0"]) - numeric_anchors[index]
                    )
                )

                if abs(float(word["x0"]) - numeric_anchors[nearest_index]) <= 55:
                    cell_words[nearest_index + 1].append(word)
                else:
                    cell_words[0].append(word)

        return [
            self._join_words(words)
            for words in cell_words
        ]

    def _join_words(self, words: list[dict]) -> str:
        if not words:
            return ""

        words = sorted(
            words,
            key=lambda item: (item["top"], item["x0"])
        )

        parts = []
        current_line = []
        current_top = None

        for word in words:
            top = float(word["top"])

            if current_top is None or abs(top - current_top) <= 3:
                current_line.append(word)
                current_top = top if current_top is None else current_top
            else:
                parts.append(
                    " ".join(
                        self._clean_cell(item["text"])
                        for item in sorted(
                            current_line,
                            key=lambda item: item["x0"]
                        )
                    )
                )
                current_line = [word]
                current_top = top

        if current_line:
            parts.append(
                " ".join(
                    self._clean_cell(item["text"])
                    for item in sorted(
                        current_line,
                        key=lambda item: item["x0"]
                    )
                )
            )

        return self._clean_cell(" ".join(parts))

    def _looks_like_header(self, cells: list[str]) -> bool:
        text = " ".join(
            self._repair_common_header_text(cell)
            for cell in cells
        ).lower()

        header_words = {
            "variable",
            "number",
            "percentage",
            "remission",
            "relapse",
            "death",
            "risk group",
            "type of",
            "study name",
        }

        return sum(word in text for word in header_words) >= 2

    def _normalize_headers(self, cells: list[str]) -> list[str]:
        headers = []

        for index, cell in enumerate(cells):
            cleaned = self._repair_common_header_text(cell)
            normalized = re.sub(r"[^a-z0-9]+", "_", cleaned.lower()).strip("_")

            if not normalized:
                normalized = "label" if index == 0 else f"value_{index}"

            headers.append(normalized)

        return headers

    def _make_unique_headers(self, headers: list[str]) -> list[str]:
        unique_headers = []
        counts = {}

        for header in headers:
            counts[header] = counts.get(header, 0) + 1

            if counts[header] == 1:
                unique_headers.append(header)
            else:
                unique_headers.append(f"{header}_{counts[header]}")

        return unique_headers

    def _repair_common_header_text(self, text: str) -> str:
        compact = re.sub(r"[^a-z]", "", text.lower())

        if "nnuummbbeerr" in compact or compact in {"numbern", "number"}:
            return "Number"

        if (
            compact.startswith("ppeer")
            or "ntataggee" in compact
            or compact.startswith("percentage")
        ):
            return "Percentage"

        if "chalenges" in compact:
            return text.replace("Chalenges", "Challenges").replace(
                "chalenges",
                "challenges"
            )

        return self._clean_cell(text)

    def _first_meaningful_label(self, rows: list[list[str]]) -> str:
        for row in rows:
            if row and row[0]:
                return row[0]
        return ""

    def _last_meaningful_label(self, rows: list[list[str]]) -> str:
        for row in reversed(rows):
            if row and row[0]:
                return row[0]
        return ""

    def _remove_generic_fragment(
        self,
        text: str,
        fragment: dict
    ) -> str:
        first_label = fragment.get("first_label", "").strip()
        last_label = fragment.get("last_label", "").strip()

        if not first_label or not last_label:
            return text

        start_pattern = self._phrase_pattern(first_label)
        end_pattern = self._phrase_pattern(last_label)

        # Include the final values from the last row when possible. This
        # prevents a short category label from ending the match too early.
        last_values = [
            value
            for value in fragment.get("last_cells", [])[1:]
            if value
        ]

        if last_values:
            end_pattern += "(?:\\s*\\n\\s*" + ")?(?:\\s*\\n\\s*".join(
                self._phrase_pattern(value)
                for value in last_values
            ) + ")?"

        pattern = re.compile(
            rf"(?ms)^\s*{start_pattern}\s*$.*?^\s*{end_pattern}\s*$"
        )

        match = pattern.search(text)

        if not match:
            return text

        return (
            text[:match.start()].rstrip()
            + "\n"
            + text[match.end():].lstrip()
        )

    def _phrase_pattern(self, value: str) -> str:
        words = re.findall(r"\S+", value)

        if not words:
            return ""

        return r"\s+".join(re.escape(word) for word in words)

    def _extract_figures_from_page(
        self,
        page,
        page_number: int
    ) -> list[dict]:
        """Extract captions while preserving side-by-side figure columns."""
        words = page.dedupe_chars(tolerance=1).extract_words(
            use_text_flow=False,
            keep_blank_chars=False
        )

        if not words:
            return []

        lines = self._group_words_into_lines(words)
        figures = []

        for line_index, line in enumerate(lines):
            line_words = line["words"]
            starts = self._find_figure_starts(line_words)

            if not starts:
                continue

            for start_index, start in enumerate(starts):
                word_index = start["word_index"]
                figure_number = start["number"]

                if start_index + 1 < len(starts):
                    next_word_index = starts[start_index + 1]["word_index"]
                    same_line_words = line_words[word_index:next_word_index]
                else:
                    same_line_words = line_words[word_index:]

                same_line_words = self._trim_caption_at_large_gap(
                    same_line_words
                )

                if len(same_line_words) < 2:
                    continue

                left_bound, right_bound = self._figure_column_bounds(
                    page_width=float(page.width),
                    starts=starts,
                    start_index=start_index,
                    same_line_words=same_line_words
                )

                caption_words = list(same_line_words)
                previous_top = float(line["top"])

                # Figure captions in these articles wrap to one or two
                # nearby lines. Stop before body text or page numbering.
                for following_line in lines[line_index + 1:line_index + 4]:
                    following_top = float(following_line["top"])

                    if following_top - previous_top > 22:
                        break

                    column_words = [
                        word
                        for word in following_line["words"]
                        if left_bound <= self._word_center_x(word) < right_bound
                    ]

                    if not column_words:
                        continue

                    if self._is_page_number_line(column_words):
                        break

                    if self._find_figure_starts(column_words):
                        break

                    caption_words.extend(column_words)
                    previous_top = following_top

                caption_text = self._join_words(caption_words)
                title = re.sub(
                    rf"^(?:Figure|Fig\.?)\s+{figure_number}"
                    rf"\s*[-:–—.]?\s*",
                    "",
                    caption_text,
                    flags=re.IGNORECASE
                ).strip()

                if not title:
                    continue

                figures.append({
                    "id": f"Figure {figure_number}",
                    "number": figure_number,
                    "title": title,
                    "page": page_number,
                    "caption": ""
                })

        return self._deduplicate_figures(figures)

    def _group_words_into_lines(
        self,
        words: list[dict],
        tolerance: float = 3.0
    ) -> list[dict]:
        sorted_words = sorted(
            words,
            key=lambda word: (
                float(word["top"]),
                float(word["x0"])
            )
        )

        lines = []

        for word in sorted_words:
            top = float(word["top"])

            if not lines or abs(top - lines[-1]["top"]) > tolerance:
                lines.append({
                    "top": top,
                    "words": [word]
                })
            else:
                lines[-1]["words"].append(word)
                line_count = len(lines[-1]["words"])
                lines[-1]["top"] = (
                    lines[-1]["top"] * (line_count - 1) + top
                ) / line_count

        for line in lines:
            line["words"].sort(key=lambda word: float(word["x0"]))

        return lines

    def _find_figure_starts(
        self,
        line_words: list[dict]
    ) -> list[dict]:
        starts = []

        for index in range(len(line_words) - 1):
            marker = self._clean_cell(line_words[index].get("text", ""))
            number_token = self._clean_cell(
                line_words[index + 1].get("text", "")
            )

            if not re.fullmatch(r"(?:Figure|Fig\.?)", marker, re.IGNORECASE):
                continue

            number_match = re.fullmatch(
                r"(\d{1,3})(?:\s*[-:–—.])?",
                number_token
            )

            if not number_match:
                continue

            # A caption marker normally uses punctuation after the number.
            # Without punctuation, only accept it near the left edge of a
            # line to avoid in-text references such as "Figure 4".
            has_separator = bool(re.search(r"[-:–—.]$", number_token))

            if not has_separator and float(line_words[index]["x0"]) > 100:
                continue

            starts.append({
                "word_index": index,
                "number": int(number_match.group(1)),
                "x0": float(line_words[index]["x0"])
            })

        return starts

    def _trim_caption_at_large_gap(
        self,
        words: list[dict],
        gap_limit: float = 18.0
    ) -> list[dict]:
        if len(words) < 2:
            return words

        trimmed = [words[0]]

        for word in words[1:]:
            previous = trimmed[-1]
            gap = float(word["x0"]) - float(previous["x1"])

            if gap > gap_limit:
                break

            trimmed.append(word)

        return trimmed

    def _figure_column_bounds(
        self,
        page_width: float,
        starts: list[dict],
        start_index: int,
        same_line_words: list[dict]
    ) -> tuple[float, float]:
        current_x = starts[start_index]["x0"]

        if start_index > 0:
            previous_x = starts[start_index - 1]["x0"]
            left_bound = (previous_x + current_x) / 2
        else:
            left_bound = 0.0

        if start_index + 1 < len(starts):
            next_x = starts[start_index + 1]["x0"]
            right_bound = (current_x + next_x) / 2
        else:
            right_bound = page_width

            # A single caption in the left column may have unrelated text in
            # the right column on the same baseline. Keep its continuation
            # inside the left half when the first line ends near the centre.
            last_x = max(float(word["x1"]) for word in same_line_words)
            midpoint = page_width / 2

            if current_x < midpoint and last_x <= midpoint + 5:
                right_bound = midpoint + 5

        return left_bound, right_bound

    def _is_page_number_line(self, words: list[dict]) -> bool:
        return (
            len(words) == 1
            and bool(re.fullmatch(
                r"\d{1,3}",
                self._clean_cell(words[0].get("text", ""))
            ))
        )

    def _word_center_x(self, word: dict) -> float:
        return (
            float(word["x0"])
            + float(word["x1"])
        ) / 2

    def _deduplicate_figures(
        self,
        figures: list[dict]
    ) -> list[dict]:
        unique = []
        seen = set()

        for figure in figures:
            key = (
                figure["page"],
                figure["number"],
                figure["title"]
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(figure)

        return unique

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

    def _is_numeric_token(self, value: str) -> bool:
        value = value.strip()

        return bool(re.fullmatch(
            r"(?:"
            r"(?:[<>≤≥]?\s*)?\d+(?:\.\d+)?"
            r"(?:\s*\([^)]*%?\))?%?"
            r"|\(\d+(?:\.\d+)?%\)"
            r")",
            value
        ))

    def _convert_generic_value(self, value: str) -> Any:
        value = self._clean_cell(value)

        if not value:
            return None

        if re.fullmatch(r"-?\d+", value):
            return int(value)

        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)

        return value

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

    def _merge_close_values(
        self,
        values: list[float],
        tolerance: float
    ) -> list[float]:
        if not values:
            return []

        values = sorted(values)
        groups = [[values[0]]]

        for value in values[1:]:
            if value - groups[-1][-1] <= tolerance:
                groups[-1].append(value)
            else:
                groups.append([value])

        return [
            sum(group) / len(group)
            for group in groups
        ]

    def _word_center_y(self, word: dict) -> float:
        return (
            float(word["top"])
            + float(word["bottom"])
        ) / 2

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
