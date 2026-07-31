import re


class TextCleaner:

    def clean_text(self, text: str) -> str:

        # Normalize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # ------------------------------------
        # Remove page numbers inside words
        # Example:
        # sur
        # 3 vival
        # ->
        # survival
        # ------------------------------------
        text = re.sub(
            r"([a-zA-Z])\s*\n\s*\d+\s*([a-zA-Z])",
            r"\1\2",
            text
        )


        # ------------------------------------
        # Fix hyphenated words split by PDF
        # Example:
        # im-
        # pact
        # ->
        # impact
        # ------------------------------------
        text = re.sub(
            r"(\w+)-\s*\n\s*(\w+)",
            r"\1\2",
            text
        )


        # ------------------------------------
        # Join normal wrapped lines
        # Example:
        # checkpoint inhibitors
        # which improved
        #
        # ->
        #
        # checkpoint inhibitors which improved
        # ------------------------------------
        text = re.sub(
            r"(?<=[a-z,])\n(?=[a-z])",
            " ",
            text
        )


        # ------------------------------------
        # Clean line spaces
        # ------------------------------------
        lines = [
            line.strip()
            for line in text.split("\n")
        ]

        text = "\n".join(lines)


        # Remove multiple empty lines
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )


        # Remove multiple spaces
        text = re.sub(
            r"[ \t]+",
            " ",
            text
        )


        return text.strip()


    def clean_pages(self, pages: list[str]) -> str:

        cleaned_pages = []

        for page in pages:
            cleaned = self.clean_text(page)

            if cleaned:
                cleaned_pages.append(cleaned)


        text = "\n\n".join(cleaned_pages)


        # Fix words split between pages
        text = re.sub(
            r"(\w+)-\s*\n+\s*(\w+)",
            r"\1\2",
            text
        )


        # Remove standalone page numbers
        text = re.sub(
            r"\n\s*\d+\s*\n",
            "\n",
            text
        )


        return text.strip()
