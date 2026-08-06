import re
from pathlib import Path

import fitz


class ArticleExtractor:

    def extract(
        self,
        text: str,
        reference_text=None,
        pdf_path: str | Path | None = None
    ):

        reference_source = (
            reference_text
            if reference_text is not None
            else text
        )



        references = self.extract_references(reference_source)

        # Some two-column PDFs store the visible reference numbers and
        # citation text in separate positioned blocks. In that layout, the
        # normal sequential-text parser cannot reconstruct the references.
        if not references and pdf_path is not None:
            references = self.extract_references_from_pdf(pdf_path)

        return {
            "metadata": {
                "title": self.extract_title(text),
                "article_type": self.extract_article_type(text),
                "authors": self.extract_authors(text),
                "correspondence": self.extract_correspondence(text),
                "affiliations": self.extract_affiliations(text),
                "published_date": self.extract_date(text),
                "doi": self.extract_doi(text)
            },
            "article_text": self.extract_body(text),
            "references": references
        }


    def _get_front_matter(self, text):

        body_headings = [
            "SUMMARY",
            "ABSTRACT",
            "INTRODUCTION",
            "BACKGROUND"
        ]

        end_positions = []

        for heading in body_headings:
            match = re.search(
                rf"(?m)^{heading}\s*$",
                text,
                re.IGNORECASE
            )

            if match:
                end_positions.append(match.start())

        if end_positions:
            return text[:min(end_positions)]

        return text


    def extract_title(self, text):

        front_matter = self._get_front_matter(text)

        lines = [
            line.strip()
            for line in front_matter.splitlines()
            if line.strip()
        ]

        while lines and lines[0].isdigit():
            lines = lines[1:]

        metadata_pattern = re.compile(
            r"^(?:authors?|correspondence|corresponding authors?|"
            r"affiliations?|published|doi)\s*:",
            re.IGNORECASE
        )

        article_type_pattern = re.compile(
            r"^(?:mini review|review|original article|article|"
            r"case report|editorial|letter|commentary)$",
            re.IGNORECASE
        )

        first_metadata_index = next(
            (
                index
                for index, line in enumerate(lines)
                if metadata_pattern.match(line)
            ),
            None
        )

        # Layout 1: title appears before the metadata block.
        if first_metadata_index not in (None, 0):
            return " ".join(lines[:first_metadata_index]).strip()

        # Layout 2: title appears after the Published field.
        published_index = next(
            (
                index
                for index, line in enumerate(lines)
                if re.match(r"^Published\s*:", line, re.IGNORECASE)
            ),
            None
        )

        if published_index is not None:
            title_lines = []

            for line in lines[published_index + 1:]:

                if (
                    metadata_pattern.match(line)
                    or article_type_pattern.fullmatch(line)
                ):
                    break

                title_lines.append(line)

            if title_lines:
                return " ".join(title_lines).strip()

        return ""


    def extract_article_type(self, text):

        front_matter = self._get_front_matter(text)

        article_types = [
            "mini review",
            "original article",
            "case report",
            "review",
            "article",
            "editorial",
            "letter",
            "commentary"
        ]

        for article_type in article_types:
            if re.search(
                rf"\b{re.escape(article_type)}\b",
                front_matter,
                re.IGNORECASE
            ):
                return article_type

        return ""


    def extract_authors(self, text):

        match = re.search(
            r"(?m)^Authors?\s*:\s*(.+)$",
            text,
            re.IGNORECASE
        )

        if match:
            return [match.group(1).strip()]

        return []


    def extract_correspondence(self, text):

        match = re.search(
            r"(?m)^(?:Correspondence|Corresponding Authors?|"
            r"Correspondence to|For correspondence|Contact Author)"
            r"\s*:\s*(.+)$",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

        return ""


    def extract_affiliations(self, text):

        front_matter = self._get_front_matter(text)

        # Explicit Affiliation/Affiliations label.
        explicit_match = re.search(
            r"(?ms)^Affiliations?\s*:\s*(.*?)"
            r"(?=^Published\s*:|^DOI\s*:|\Z)",
            front_matter,
            re.IGNORECASE
        )

        if explicit_match:
            affiliation = " ".join(
                line.strip()
                for line in explicit_match.group(1).splitlines()
                if line.strip()
            )

            return [affiliation] if affiliation else []

        # Fallback for layouts where affiliation lines follow
        # correspondence without an Affiliation label.
        match = re.search(
            r"(?ms)^(?:Correspondence|Corresponding Authors?)"
            r"\s*:[^\n]*\n(.*?)^Published\s*:",
            front_matter,
            re.IGNORECASE
        )

        if not match:
            return []

        affiliations = []

        for line in match.group(1).splitlines():
            clean_line = line.strip()

            if clean_line and clean_line not in affiliations:
                affiliations.append(clean_line)

        return affiliations


    def extract_date(self, text):

        # Try Published:
        match = re.search(
            r"Published:\s*(.+)",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()



        match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
            text
        )

        if match:
            return match.group(0)


        return ""


    def extract_doi(self, text):

        match = re.search(
            r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
            text,
            re.IGNORECASE
        )

        if match:
            return "https://doi.org/" + match.group(1)

        return ""


    def extract_body(self, text):

        # Common first article sections
        start_patterns = [
            r"\bSUMMARY\b",
            r"\bABSTRACT\b",
            r"\bINTRODUCTION\b",
            r"\bBACKGROUND\b"
        ]

        start = None

        for pattern in start_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.start()
                break

        if start is None:
            return ""

        body = text[start:]

        body = re.sub(
            r"Evolution of the treatment of.*?Published:.*?(?:\n|$)",
            "",
            body,
            flags=re.IGNORECASE | re.DOTALL
        )

        # Remove references section
        references_match = re.search(
            r"\bREFERENCES\b",
            body,
            re.IGNORECASE
        )

        if references_match:
            body = body[:references_match.start()]

        body = re.sub(r"-\n(?=[a-z])", "", body)
        return body.strip()


    def extract_references(self, text):

        match = re.search(
            r"\bREFERENCES\b(.*)",
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            return []

        references_text = match.group(1).strip()

        # Find possible reference numbers.
        candidates = list(
            re.finditer(
                r"(?m)^(\d{1,3})\.\s+",
                references_text
            )
        )

        # Accept only sequential reference numbers.
        # This prevents page ranges such as "26."
        # from being treated as a new reference.
        reference_matches = []
        expected_number = 1

        for candidate in candidates:

            number = int(candidate.group(1))

            if number == expected_number:
                reference_matches.append(candidate)
                expected_number += 1

        references = []

        for index, reference_match in enumerate(reference_matches):

            number = int(reference_match.group(1))
            content_start = reference_match.end()

            if index + 1 < len(reference_matches):
                content_end = reference_matches[index + 1].start()
            else:
                content_end = len(references_text)

            reference_text = references_text[
                content_start:content_end
            ]

            clean_reference = self._clean_reference_text(
                reference_text
            )

            if clean_reference:
                references.append(
                    self._structure_reference(
                        number,
                        clean_reference
                    )
                )

        return references


    def _clean_reference_text(self, reference):

        # Remove standalone PDF page numbers.
        reference = re.sub(
            r"(?m)^\s*\d{1,3}\s*$",
            "",
            reference
        )

        # Join words split by a line break:
        # Inter-\nleukin -> Interleukin
        reference = re.sub(
            r"-\s*\n\s*(?=[a-z])",
            "",
            reference
        )

        # Preserve real hyphens before uppercase words:
        # Wild-\nType -> Wild-Type
        reference = re.sub(
            r"-\s*\n\s*(?=[A-Z])",
            "-",
            reference
        )

        reference = " ".join(
            line.strip()
            for line in reference.splitlines()
            if line.strip()
        )

        reference = re.sub(
            r"\s+",
            " ",
            reference
        ).strip()

        # Example: 2517– 26 -> 2517–26
        reference = re.sub(
            r"([–-])\s+(?=\d)",
            r"\1",
            reference
        )

        # Remove license text appended to the final reference.
        reference = re.sub(
            r"\s*Licensed under CC BY 4\.0.*$",
            "",
            reference,
            flags=re.IGNORECASE
        )

        return reference.strip()


    def extract_references_from_pdf(
        self,
        pdf_path: str | Path
    ) -> list[dict]:
        """Extract references from positioned two-column PDF blocks."""
        document = fitz.open(str(pdf_path))

        try:
            references_page = self._find_references_page(document)

            if references_page is None:
                return []

            markers = []
            text_blocks = []

            for page_index in range(references_page, len(document)):
                page = document[page_index]
                page_width = float(page.rect.width)
                page_height = float(page.rect.height)

                for block in page.get_text("blocks", sort=False):
                    x0, y0, x1, _, block_text, *_ = block
                    clean_text = self._clean_pdf_reference_block(block_text)

                    if not clean_text:
                        continue

                    column = 0 if x0 < page_width / 2 else 1
                    number = self._reference_marker_number(clean_text)

                    block_data = {
                        "page": page_index,
                        "column": column,
                        "y": float(y0),
                        "x": float(x0),
                        "text": clean_text,
                    }

                    is_number_marker = (
                        number is not None
                        and 1 <= number <= 999
                        and float(x1) - float(x0) < 35
                        and float(y0) < page_height - 44
                    )

                    if is_number_marker:
                        block_data["number"] = number
                        markers.append(block_data)
                    else:
                        text_blocks.append(block_data)

            sequential_markers = self._select_sequential_markers(markers)

            if len(sequential_markers) < 2:
                return []

            references = []

            for number in range(1, len(sequential_markers) + 1):
                start_marker = sequential_markers[number]
                end_marker = sequential_markers.get(number + 1)

                reference_text = self._collect_reference_blocks(
                    text_blocks=text_blocks,
                    start_marker=start_marker,
                    end_marker=end_marker
                )

                if reference_text:
                    references.append(
                        self._structure_reference(
                            number,
                            reference_text
                        )
                    )

            return references

        finally:
            document.close()


    def _clean_pdf_reference_block(self, text: str) -> str:
        text = text.replace("\u00a0", " ")
        text = re.sub(r"-\s*\n\s*(?=[a-z])", "", text)
        text = re.sub(r"-\s*\n\s*(?=[A-Z])", "-", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


    def _find_references_page(self, document) -> int | None:
        for page_index, page in enumerate(document):
            if re.search(
                r"(?m)^\s*REFERENCES\s*$",
                page.get_text(),
                re.IGNORECASE
            ):
                return page_index

        return None


    def _reference_marker_number(self, text: str) -> int | None:
        match = re.fullmatch(r"(\d{1,3})\.?", text.strip())

        if match:
            return int(match.group(1))

        return None


    def _select_sequential_markers(
        self,
        markers: list[dict]
    ) -> dict[int, dict]:
        markers.sort(key=self._reference_flow_key)

        selected = {}
        expected_number = 1

        for marker in markers:
            if marker["number"] != expected_number:
                continue

            selected[expected_number] = marker
            expected_number += 1

        return selected


    def _collect_reference_blocks(
        self,
        text_blocks: list[dict],
        start_marker: dict,
        end_marker: dict | None
    ) -> str:
        start_key = self._reference_flow_key(start_marker)

        if end_marker is None:
            end_key = (10**9, 0, 0.0, 0.0)
        else:
            end_key = self._reference_flow_key(end_marker)

        candidate_blocks = [
            block
            for block in text_blocks
            if start_key <= self._reference_flow_key(block) < end_key
        ]

        candidate_blocks.sort(key=self._reference_flow_key)

        accepted_text = []

        for block in candidate_blocks:
            block_text = block["text"]

            if self._is_reference_noise(block_text):
                continue

            if block_text.upper() == "REFERENCES":
                continue

            if (
                self._looks_like_reference_author(block_text)
                or self._contains_bibliographic_ending(block_text)
            ):
                accepted_text.append(block_text)

        reference = self._clean_reference_text(
            " ".join(accepted_text)
        )

        return reference.lstrip(". ")


    def _reference_flow_key(self, block: dict) -> tuple:
        return (
            block["page"],
            block["column"],
            block["y"],
            block["x"]
        )


    def _looks_like_reference_author(self, text: str) -> bool:
        text = text.lstrip(". ")

        return bool(re.match(
            r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+"
            r"(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’.-]*){1,4}"
            r"(?:\s+(?:Jr|Sr))?\s*,",
            text
        ))


    def _contains_bibliographic_ending(self, text: str) -> bool:
        standard_ending = re.search(
            r"\b(?:19|20)\d{2}\b"
            r"(?:\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|"
            r"Oct|Nov|Dec)(?:\s+\d{1,2})?)?"
            r"\s*;\s*\d+",
            text,
            re.IGNORECASE
        )

        year_ending = re.search(
            r"\b(?:19|20)\d{2}\.?$",
            text
        )

        return bool(standard_ending or year_ending)


    def _is_reference_noise(self, text: str) -> bool:
        text_lower = text.lower()

        noise_phrases = [
            "creative commons",
            "to view a copy of this license",
            "the author(s) 2024",
            "oncology medical journal",
        ]

        return any(
            phrase in text_lower
            for phrase in noise_phrases
        )


    def _structure_reference(self, number, reference):

        structured_reference = {
            "number": number,
            "authors": [],
            "title": "",
            "journal": "",
            "year": None,
            "month": None,
            "day": None,
            "volume": None,
            "issue": None,
            "pages": "",
            "raw": f"{number}. {reference}"
        }

        months = (
            r"Jan|Feb|Mar|Apr|May|Jun|"
            r"Jul|Aug|Sep|Oct|Nov|Dec"
        )

        date_match = re.search(
            rf"(?P<year>\d{{4}})"
            rf"(?:\s+(?P<month>{months}))?"
            rf"(?:\s+(?P<day>\d{{1,2}}))?"
            rf"(?:\s*;\s*(?P<volume>\d+)"
            rf"(?:\((?P<issue>[^)]+)\))?"
            rf"\s*:\s*(?P<pages>.+?))?"
            rf"\.?$",
            reference,
            re.IGNORECASE
        )

        if not date_match:
            return structured_reference

        before_date = reference[:date_match.start()].rstrip(" .;,")

        authors_text, citation_body = self._split_reference_authors(
            before_date
        )

        if not authors_text or not citation_body:
            return structured_reference

        title, journal = self._split_reference_title_journal(
            citation_body
        )

        if not title or not journal:
            return structured_reference

        authors = [
            author.strip()
            for author in re.split(r"[,;]", authors_text)
            if author.strip()
        ]

        volume = date_match.group("volume")
        day = date_match.group("day")
        pages = date_match.group("pages") or ""

        structured_reference.update({
            "authors": authors,
            "title": title,
            "journal": journal,
            "year": int(date_match.group("year")),
            "month": (
                date_match.group("month").title()
                if date_match.group("month")
                else None
            ),
            "day": int(day) if day else None,
            "volume": int(volume) if volume else None,
            "issue": date_match.group("issue"),
            "pages": pages.strip().rstrip(".")
        })

        return structured_reference


    def _split_reference_authors(
        self,
        before_date: str
    ) -> tuple[str, str]:
        et_al_colon = re.match(
            r"^(?P<authors>.+?et al\.)\s*:\s*(?P<body>.+)$",
            before_date,
            re.IGNORECASE
        )

        if et_al_colon:
            return (
                et_al_colon.group("authors"),
                et_al_colon.group("body")
            )

        et_al_period = re.match(
            r"^(?P<authors>.+?et al\.)\s+(?P<body>.+)$",
            before_date,
            re.IGNORECASE
        )

        if et_al_period:
            return (
                et_al_period.group("authors"),
                et_al_period.group("body")
            )

        first_period = re.match(
            r"^(?P<authors>.+?\.)\s+(?P<body>.+)$",
            before_date
        )

        if first_period:
            return (
                first_period.group("authors").rstrip("."),
                first_period.group("body")
            )

        return "", ""


    def _split_reference_title_journal(
        self,
        citation_body: str
    ) -> tuple[str, str]:
        match = re.match(
            r"^(?P<title>.+[.?!])\s+(?P<journal>[^.?!]+)$",
            citation_body
        )

        if not match:
            return "", ""

        title = match.group("title").strip().rstrip(".?!")
        journal = match.group("journal").strip().rstrip(".")

        return title, journal
