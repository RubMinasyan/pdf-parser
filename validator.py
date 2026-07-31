import json
import re
from datetime import datetime
from typing import Any


class ArticleValidator:

    def validate(
        self,
        article: dict[str, Any],
        require_complete: bool = True
    ) -> dict:

        errors = []
        warnings = []

        # Confirm that the result can be converted to JSON.
        try:
            json.dumps(article, ensure_ascii=False)
        except (TypeError, ValueError) as error:
            errors.append(
                f"Article is not JSON serializable: {error}"
            )

        metadata = article.get("metadata")

        if not isinstance(metadata, dict):
            errors.append("metadata must be an object.")
            metadata = {}

        self._check_required_value(
            metadata.get("title"),
            "metadata.title",
            errors,
            warnings,
            require_complete
        )

        self._check_required_list(
            metadata.get("authors"),
            "metadata.authors",
            errors,
            warnings,
            require_complete
        )

        self._check_required_value(
            metadata.get("correspondence"),
            "metadata.correspondence",
            errors,
            warnings,
            require_complete
        )

        self._check_required_list(
            metadata.get("affiliations"),
            "metadata.affiliations",
            errors,
            warnings,
            require_complete
        )

        self._check_required_value(
            metadata.get("published_date"),
            "metadata.published_date",
            errors,
            warnings,
            require_complete
        )

        doi = metadata.get("doi")

        self._check_required_value(
            doi,
            "metadata.doi",
            errors,
            warnings,
            require_complete
        )

        if doi and not re.fullmatch(
            r"https://doi\.org/10\.\d{4,9}/\S+",
            doi
        ):
            warnings.append(
                f"DOI has an unexpected format: {doi}"
            )

        self._validate_article_content(
            article,
            errors,
            warnings,
            require_complete
        )

        self._validate_references(
            article.get("references"),
            errors,
            warnings,
            require_complete
        )

        self._validate_tables(
            article.get("tables"),
            errors,
            warnings
        )

        self._validate_figures(
            article.get("figures"),
            errors
        )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _validate_article_content(
        self,
        article,
        errors,
        warnings,
        require_complete
    ):

        self._check_required_value(
            article.get("article_text"),
            "article_text",
            errors,
            warnings,
            require_complete
        )

        self._check_required_list(
            article.get("sections"),
            "sections",
            errors,
            warnings,
            require_complete
        )

    def _validate_references(
        self,
        references,
        errors,
        warnings,
        require_complete
    ):

        if not isinstance(references, list):
            errors.append("references must be an array.")
            return

        if not references:
            message = "references is empty."

            if require_complete:
                errors.append(message)
            else:
                warnings.append(message)

            return

        expected_numbers = list(
            range(1, len(references) + 1)
        )

        actual_numbers = [
            reference.get("number")
            for reference in references
            if isinstance(reference, dict)
        ]

        if actual_numbers != expected_numbers:
            errors.append(
                "Reference numbers are missing, duplicated, "
                "or out of order."
            )

        required_fields = [
            "number",
            "authors",
            "title",
            "journal",
            "year",
            "raw"
        ]

        for reference in references:

            if not isinstance(reference, dict):
                errors.append(
                    "Every reference must be an object."
                )
                continue

            number = reference.get("number")

            for field in required_fields:

                value = reference.get(field)

                if value in (None, "", []):
                    errors.append(
                        f"Reference {number} is missing {field}."
                    )

    def _validate_tables(
        self,
        tables,
        errors,
        warnings
    ):

        if not isinstance(tables, list):
            errors.append("tables must be an array.")
            return

        current_year = datetime.now().year

        table_ids = set()

        for table in tables:

            if not isinstance(table, dict):
                errors.append(
                    "Every table must be an object."
                )
                continue

            table_id = table.get("id")

            if not table_id:
                errors.append("A table is missing its id.")
            elif table_id in table_ids:
                errors.append(
                    f"Duplicate table id: {table_id}"
                )
            else:
                table_ids.add(table_id)

            rows = table.get("rows")

            if not isinstance(rows, list):
                errors.append(
                    f"{table_id or 'Table'} rows must be an array."
                )
                continue

            for row_index, row in enumerate(rows, start=1):

                if not isinstance(row, dict):
                    errors.append(
                        f"{table_id} row {row_index} "
                        "must be an object."
                    )
                    continue

                year = row.get("year_last_reported")

                if (
                    isinstance(year, str)
                    and year.isdigit()
                ):
                    numeric_year = int(year)

                    if (
                        numeric_year < 1900
                        or numeric_year > current_year + 1
                    ):
                        warnings.append(
                            f"{table_id} row {row_index} "
                            f"contains a suspicious year: {year}"
                        )

    def _validate_figures(
        self,
        figures,
        errors
    ):

        if not isinstance(figures, list):
            errors.append("figures must be an array.")

    def _check_required_value(
        self,
        value,
        field_name,
        errors,
        warnings,
        require_complete
    ):

        if value not in (None, ""):
            return

        message = f"{field_name} is missing."

        if require_complete:
            errors.append(message)
        else:
            warnings.append(message)

    def _check_required_list(
        self,
        value,
        field_name,
        errors,
        warnings,
        require_complete
    ):

        if not isinstance(value, list):
            errors.append(
                f"{field_name} must be an array."
            )
            return

        if value:
            return

        message = f"{field_name} is empty."

        if require_complete:
            errors.append(message)
        else:
            warnings.append(message)
