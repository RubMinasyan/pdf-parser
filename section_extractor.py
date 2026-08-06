import re


class SectionExtractor:

    SECTION_PATTERNS = [

        # ------------------------------------
        # Common main scientific sections
        # ------------------------------------
        (r"^ABSTRACT$", "ABSTRACT", 1),
        (r"^INTRODUCTION$", "INTRODUCTION", 1),
        (r"^BACKGROUND$", "BACKGROUND", 1),
        (r"^METHODOLOGY$", "METHODOLOGY", 1),
        (r"^METHODS$", "METHODS", 1),
        (
            r"^MATERIALS AND METHODS$",
            "MATERIALS AND METHODS",
            1
        ),
        (r"^RESULTS$", "RESULTS", 1),
        (r"^DISCUSSION$", "DISCUSSION", 1),
        (r"^CONCLUSION$", "CONCLUSION", 1),
        (r"^CONCLUSIONS$", "CONCLUSIONS", 1),

        # ------------------------------------
        # Post-article sections
        # ------------------------------------
        (
            r"^ACKNOWLEDGEMENTS?$",
            "ACKNOWLEDGEMENTS",
            1
        ),
        (
            r"^ACKNOWLEDGMENTS?$",
            "ACKNOWLEDGEMENTS",
            1
        ),
        (
            r"^CONFLICT OF INTERESTS?$",
            "CONFLICT OF INTEREST",
            1
        ),
        (
            r"^ETHICAL CONSIDERATIONS$",
            "ETHICAL CONSIDERATIONS",
            1
        ),
        (r"^FUNDING$", "FUNDING", 1),

        # ------------------------------------
        # Article-4 main sections
        # ------------------------------------
        (r"^SUMMARY$", "SUMMARY", 1),
        (
            r"^CONVENTIONAL THERAPIES$",
            "CONVENTIONAL THERAPIES",
            1
        ),
        (
            r"^TARGETED THERAPIES$",
            "TARGETED THERAPIES",
            1
        ),
        (
            r"^C-KIT INHIBITION$",
            "C-KIT INHIBITION",
            1
        ),
        (
            r"^CHECKPOINT INHIBITORS$",
            "CHECKPOINT INHIBITORS",
            1
        ),
        (
            r"^COMBINATION THERAPY$",
            "COMBINATION THERAPY",
            1
        ),
        (
            r"^TREATMENT OF PATIENTS\s+WITH BRAIN METASTASIS$",
            "TREATMENT OF PATIENTS WITH BRAIN METASTASIS",
            1
        ),
        (
            r"^OTHER THERAPIES FOR\s+METASTATIC MELANOMA$",
            "OTHER THERAPIES FOR METASTATIC MELANOMA",
            1
        ),

        # ------------------------------------
        # Common / RMS subsections
        #
        # The fourth value True means the
        # capitalization must match exactly.
        # ------------------------------------
        (
            r"^Chemotherapy$",
            "Chemotherapy",
            2,
            True
        ),
        (
            r"^Evaluation and Follow[-\s]?up$",
            "Evaluation and Follow-up",
            2,
            True
        ),
        (
            r"^Operational definitions$",
            "Operational definitions",
            2,
            True
        ),
        (
            r"^Statistical Analysis$",
            "Statistical Analysis",
            2,
            True
        ),
        (
            r"^Challenges$",
            "Challenges",
            2,
            True
        ),

        # ------------------------------------
        # Article-4 subsections
        # ------------------------------------
        (
            r"^BRAF inhibitors$",
            "BRAF inhibitors",
            2
        ),
        (
            r"^MEK inhibitors$",
            "MEK inhibitors",
            2
        ),
        (
            r"^BRAF-MEK inhibitor\s+combinations$",
            "BRAF-MEK inhibitor combinations",
            2
        ),
        (
            r"^Dabrafenib plus Trametinib$",
            "Dabrafenib plus Trametinib",
            2
        ),
        (
            r"^Vemurafenib plus Cobimetinib$",
            "Vemurafenib plus Cobimetinib",
            2
        ),
        (
            r"^Anti-CTLA-4 Antibody$",
            "Anti-CTLA-4 Antibody",
            2
        ),
        (
            r"^PD-\s*1 Blockers$",
            "PD-1 Blockers",
            2
        ),
        (
            r"^Nivolumab$",
            "Nivolumab",
            2
        ),
        (
            r"^CTLA-4 Blockade and PD-[l1]\s+Blockade Combination$",
            "CTLA-4 Blockade and PD-1 Blockade Combination",
            2
        ),
        (
            r"^Patients with BRAF 600E positive\s+melanoma with brain metastases$",
            "Patients with BRAF 600E positive melanoma with brain metastases",
            2
        ),
        (
            r"^Patients with metastatic melanoma to the brain irrespective of\s+BRAF mutation$",
            "Patients with metastatic melanoma to the brain irrespective of BRAF mutation",
            2
        ),
        (
            r"^Tumor-infiltrating lymphocyte\s+\(TIL\) therapy$",
            "Tumor-infiltrating lymphocyte (TIL) therapy",
            2
        ),
        (
            r"^CAR-T cell therapy$",
            "CAR-T cell therapy",
            2
        ),
        (
            r"^New studies$",
            "New studies",
            2
        ),
    ]


    def extract_sections(
        self,
        article_text: str
    ) -> list[dict]:

        if not article_text:
            return []

        heading_matches = []

        for section_pattern in self.SECTION_PATTERNS:

            pattern, title, level = section_pattern[:3]

            case_sensitive = (
                len(section_pattern) == 4
                and section_pattern[3] is True
            )

            flags = re.MULTILINE

            if not case_sensitive:
                flags |= re.IGNORECASE

            matches = re.finditer(
                pattern,
                article_text,
                flags
            )

            for match in matches:
                heading_matches.append({
                    "start": match.start(),
                    "end": match.end(),
                    "title": title,
                    "level": level
                })

        heading_matches.sort(
            key=lambda item: item["start"]
        )

        filtered_matches = []
        seen_single_occurrence_titles = set()

        single_occurrence_titles = {
            "Nivolumab"
        }

        for match in heading_matches:

            if (
                filtered_matches
                and match["start"]
                < filtered_matches[-1]["end"]
            ):
                continue

            if match["title"] in single_occurrence_titles:

                if (
                    match["title"]
                    in seen_single_occurrence_titles
                ):
                    continue

                seen_single_occurrence_titles.add(
                    match["title"]
                )

            filtered_matches.append(match)

        sections = []

        for index, heading in enumerate(
            filtered_matches
        ):

            content_start = heading["end"]

            if index + 1 < len(filtered_matches):
                content_end = (
                    filtered_matches[index + 1]["start"]
                )
            else:
                content_end = len(article_text)

            section_text = article_text[
                content_start:content_end
            ].strip()

            sections.append({
                "title": heading["title"],
                "level": heading["level"],
                "text": section_text
            })

        return sections
