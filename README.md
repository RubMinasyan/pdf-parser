# Scientific PDF Parser

A Python parser that converts a scientific article PDF into structured JSON.

The parser extracts:

* Article metadata
* Title and article type
* Authors
* Correspondence email
* Affiliations
* Published date
* DOI
* Article body
* Article sections and subsections
* Tables with structured headers and rows
* Figure metadata
* Structured references
* Validation warnings and errors

##Installation

Clone the repository:

```bash
git clone https://github.com/RubMinasyan/YOUR-REPOSITORY.git
cd pdf_parser_project
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```


Upgrade pip and install the dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the Parser

Parse the complete PDF:

```bash
python main.py all
```

Parse one page:

```bash
python main.py 1
```

Parse a page range:

```bash
python main.py 2-6
```

## Validate the JSON File

```bash
python -m json.tool output/Article-4.json > /dev/null \
  && echo "JSON file is valid"
```

