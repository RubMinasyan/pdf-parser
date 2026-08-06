Scientific PDF Parser

The parser extracts:

    Article metadata

        Title

        Article type

        Authors

        Corresponding author or correspondence details

        Affiliations

        Published date

        DOI

    Cleaned article text

    Main sections and subsections

    Structured tables

        Specialized six-column clinical-study tables

        Generic tables with different column layouts

        Tables that continue across pages

        Captions placed above or below tables

    Figure metadata and multiline captions

    Structured references

        Standard sequential references

        Coordinate-based fallback for difficult multi-column layouts

    Validation errors and warnings


Place PDF files inside the input/ directory. Generated JSON files are written to the output/ directory.
Installation

Clone the repository:

git clone https://github.com/RubMinasyan/pdf-parser.git
cd pdf-parser

Create and activate a virtual environment:

python3 -m venv venv
source venv/bin/activate

Upgrade pip and install the dependencies:

python -m pip install --upgrade pip
pip install -r requirements.txt

##Usage
##Interactive mode

#Run the parser without arguments:

python main.py

#The program asks for the exact PDF filename from the input/ directory,
#Enter the exact PDF filename from input/ (example: RMS.pdf):

Example input:

RMS.pdf

##Direct mode

#Parse a complete PDF:

python main.py RMS.pdf

python main.py Article-4.pdf

##Select pages

#Parse one page:

python main.py RMS.pdf 3

#Parse a page range:

python main.py RMS.pdf 2-5

#Explicitly parse all pages:

python main.py RMS.pdf all

The filename must:

    End with .pdf

    Match an existing file inside input/

    Be provided as a filename only, not as a full path

Output

For an input file named:

RMS.pdf

the parser creates:

output/RMS.json
output/RMS_validation.json

## Validate Generated JSON Manually

python -m json.tool output/RMS.json > /dev/null \
  && echo "JSON file is valid"
