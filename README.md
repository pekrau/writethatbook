# WriteThatBook

Write books in a web-based app using Markdown files allowing
references and indexing, creating DOCX or PDF.

- Contents hierarchically organized into sections (directories) and texts (files).
- Content files in Markdown format.
- Reference handling.
- Indexing of terms.
- Footnotes.
- Export contents to DOCX or PDF file.

## Installation notes

Environment variables:

- WRITETHATBOOK_DIR: Absolute path to the directory containing the books. Required.
- WRITETHATBOOK_USER: User name for the administrator user. Required.
- WRITETHATBOOK_PASSWORD: Password for the administrator user. Required.
- WRITETHATBOOK_DEVELOPMENT: When defined, puts app into development mode. Optional.
- WRITETHATBOOK_APIKEY: When defined, allows using a http request header entry
  'apikey' for access. Optional.

## Software

This code has been lovingly hand-crafted. No AI tools were used in its development.

Written in [Python](https://www.python.org/) using:

- [FastHTML](https://fastht.ml/)
- [pico CSS](https://picocss.com/)
- [Marko](https://marko-py.readthedocs.io/)
- [python-docx](https://python-docx.readthedocs.io/en/latest/)
- [fpdf2](https://py-pdf.github.io/fpdf2/)
- [PyYAML](https://pypi.org/project/PyYAML/)
- [bibtexparser](https://pypi.org/project/bibtexparser/)
