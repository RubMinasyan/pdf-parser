import re


class ArticleExtractor:

    def extract(self, text: str, reference_text=None):

        reference_source = (
            reference_text
            if reference_text is not None
            else text
        )



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
            "references": self.extract_references(reference_source)
        }


    def extract_title(self, text):

        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip()
        ]

        # Skip possible page number
        if lines and lines[0].isdigit():
            lines = lines[1:]

        title_lines = []

        for line in lines:

            # Stop when metadata starts
            if (
                line.lower().startswith("author")
                or line.lower().startswith("correspondence")
                or line.lower().startswith("published")
            ):
                break

            if line.lower() not in [
                "mini review",
                "review",
                "original article"
            ]:
                title_lines.append(line)

        return " ".join(title_lines)

    def extract_article_type(self, text):

        article_types = [
            "mini review",
            "review",
            "original article",
            "case report",
            "editorial",
            "letter",
            "commentary"
        ]

        text_lower = text.lower()


        for article_type in article_types:
            if article_type in text_lower:
                return article_type
        return ""

    def extract_authors(self, text):

        match = re.search(
            r"Author:\s*(.+)",
            text,
            re.IGNORECASE
        )

        if match:
            return [
                match.group(1).strip()
            ]

        return []


    def extract_correspondence(self, text):

        match = re.search(
            r"Correspondence:\s*(.+)",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

        return ""


    def extract_affiliations(self, text):

        match = re.search(
            r"^Correspondence:[^\n]*\n(.*?)^Published:",
            text,
            re.IGNORECASE | re.MULTILINE | re.DOTALL
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

        citation_match = re.match(
            rf"^(?P<before>.+)\.\s+"
            rf"(?P<year>\d{{4}})"
            rf"(?:\s+(?P<month>{months}))?"
            rf"(?:\s+(?P<day>\d{{1,2}}))?"
            rf";(?P<volume>\d+)"
            rf"(?:\((?P<issue>[^)]+)\))?"
            rf":(?P<pages>.+?)\.?$",
            reference
        )

        if not citation_match:
            return structured_reference

        before_date = citation_match.group("before")

        # Separate the journal from authors and article title.
        journal_match = re.match(
            r"^(?P<authors_title>.+[.?!])\s+"
            r"(?P<journal>[^.!?]+)$",
            before_date
        )

        if not journal_match:
            return structured_reference

        authors_title = journal_match.group("authors_title")

        # References containing "et al."
        authors_match = re.match(
            r"^(?P<authors>.+?et al\.)\s+"
            r"(?P<title>.+)$",
            authors_title
        )

        # References listing all authors.
        if not authors_match:
            authors_match = re.match(
                r"^(?P<authors>.+?\.)\s+"
                r"(?P<title>.+)$",
                authors_title
            )

        if not authors_match:
            return structured_reference

        authors_text = authors_match.group("authors").rstrip(".")

        authors = [
            author.strip()
            for author in authors_text.split(",")
            if author.strip()
        ]

        structured_reference.update({
            "authors": authors,
            "title": authors_match.group("title").strip().rstrip("."),
            "journal": journal_match.group("journal").strip(),
            "year": int(citation_match.group("year")),
            "month": citation_match.group("month"),
            "day": (
                int(citation_match.group("day"))
                if citation_match.group("day")
                else None
            ),
            "volume": int(citation_match.group("volume")),
            "issue": citation_match.group("issue"),
            "pages": citation_match.group("pages").strip()
        })

        return structured_reference
