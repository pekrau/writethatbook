# WriteThatBook

Web app for writing books using Markdown files allowing references and
indexing, creating DOCX or PDF.

- Contents hierarchically organized into sections (directories) and texts (files).
- Content files in Markdown format.
- Interactive editing and rearrangement of sections and texts.
- Reference handling.
- Indexing of terms.
- Footnotes.
- Export contents to DOCX or PDF file.

## Installation notes

Environment variables:

- WRITETHATBOOK_DIR: Absolute path to the directory containing the data. Required.
- WRITETHATBOOK_USERID: User name for the administrator user. Required
  at initialization of a new instance for creating the first account.
- WRITETHATBOOK_PASSWORD: Password for the administrator user.
  Required at initialization of a new instance for creating the first account.
- WRITETHATBOOK_DEVELOPMENT: When defined, puts app into development mode. Optional.

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
