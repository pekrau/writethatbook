"Constants."

import functools
from pathlib import Path
import re

import babel.dates

SOFTWARE = "WriteThatBook"
VERSION = (1, 20, 0)
__version__ = ".".join([str(n) for n in VERSION])


LANGUAGE_CODES = ("sv-SE", "en-GB", "en-US")
ENCODING = "utf-8"
DEFAULT_LOCALE = "sv_SE"
DEFAULT_TIMEZONE = babel.dates.get_timezone("Europe/Stockholm")

MARKDOWN_EXT = ".md"
SOURCE_DIRPATH = Path(__file__).parent
TRANSLATIONS_FILEPATH = SOURCE_DIRPATH / "translations.csv"

USERS_DATABASE_FILENAME = "users.yaml"
MIN_PASSWORD_LENGTH = 6

SYSTEM_USERID = "system"

# User roles.
ADMIN_ROLE = "admin"
USER_ROLE = "user"
ROLES = (ADMIN_ROLE, USER_ROLE)

# Item types
TEXT = "text"
SECTION = "section"

DATETIME_ISO_FORMAT = "%Y-%m-%d %H:%M:%S"
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
EM_DASH = "\u2014"


@functools.total_ordering
class Status:
    @classmethod
    def lookup(cls, name, default=None):
        if name:
            return STATUS_LOOKUP.get(name) or default
        else:
            return min(STATUSES)

    def __init__(self, name, ordinal, color):
        self.name = name
        self.ordinal = ordinal
        self.color = color

    def __str__(self):
        return self.name.capitalize()

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        if not isinstance(other, Status):
            return False
        return self.name == other.name

    def __ne__(self, other):
        return other is None or self.name != other.name

    def __lt__(self, other):
        return self.ordinal < other.ordinal


STARTED = Status("started", 0, "green")
DRAFT = Status("draft", 1, "crimson")
MANUSCRIPT = Status("manuscript", 2, "dodgerblue")
REVISED = Status("revised", 3, "blueviolet")
FINAL = Status("final", 4, "black")
OMITTED = Status("omitted", 5, "silver")
STATUSES = (STARTED, DRAFT, MANUSCRIPT, REVISED, FINAL, OMITTED)
STATUS_LOOKUP = dict([(s.name, s) for s in STATUSES])
STATUS_LOOKUP.update(dict([(str(s), s) for s in STATUSES]))

ARTICLE = "article"
BOOK = "book"
LINK = "link"

MAX_RECENT = 20
MAX_COPY_NUMBER = 20

REFS = "_refs"
REFS_TYPES = (ARTICLE, BOOK, LINK)
REFS_COLOR = "royalblue"
REFS_LINKS = dict(
    doi=("DOI", "https://doi.org/{value}"),
    pmid=("PubMed", "https://pubmed.ncbi.nlm.nih.gov/{value}"),
    isbn=("ISBN", "https://isbnsearch.org/isbn/{value}"),
)
MAX_DISPLAY_AUTHORS = 4

IMGS = "_imgs"

NORMAL = "normal"
ITALIC = "italic"
BOLD = "bold"
UNDERLINE = "underline"
FONT_STYLES = (NORMAL, ITALIC, BOLD, UNDERLINE)

CHUNK_PATTERN = re.compile(r"\n$\n", re.M)

MAX_LEVEL = 6

FOOTNOTES_EACH_TEXT = "after each text"
FOOTNOTES_EACH_CHAPTER = "after each chapter"
FOOTNOTES_END_OF_BOOK = "at end of book"
FOOTNOTES_LOCATIONS = (
    FOOTNOTES_EACH_TEXT,
    FOOTNOTES_EACH_CHAPTER,
    FOOTNOTES_END_OF_BOOK,
)

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_CONTENT_TYPE = "application/pdf"
GZIP_CONTENT_TYPE = "application/gzip"
SVG_CONTENT_TYPE = "image/svg+xml"
JSON_CONTENT_TYPE = "application/json"
PNG_CONTENT_TYPE = "image/png"
JPEG_CONTENT_TYPE = "image/jpeg"

IMAGE_MAP = {
    SVG_CONTENT_TYPE: "SVG",
    JSON_CONTENT_TYPE: "Vega-Lite",
    PNG_CONTENT_TYPE: "PNG",
    JPEG_CONTENT_TYPE: "JPEG",
}

SVG_XMLNS = "http://www.w3.org/2000/svg"

DOCX_MAX_PAGE_BREAK_LEVEL = 4
DOCX_MAX_TOC_LEVEL = 4
DOCX_TOC_INDENT = 15
DOCX_TOC_SPACE_BEFORE = 0
DOCX_TOC_SPACE_AFTER = 0
DOCX_NORMAL_FONT = "Arial"
DOCX_NORMAL_FONT_SIZE = 12
DOCX_NORMAL_LINE_SPACING = 17
DOCX_SYNOPSIS_INDENT = 16
DOCX_SYNOPSIS_LINE_SPACING = 15
DOCX_SYNOPSIS_SPACE_BEFORE = 10
DOCX_SYNOPSIS_SPACE_AFTER = 10
DOCX_QUOTE_INDENT = 16
DOCX_CODE_FONT = "Courier"
DOCX_CODE_FONT_SIZE = 11
DOCX_CODE_LINE_SPACING = 12
DOCX_CODE_INDENT = 10
DOCX_FOOTNOTE_INDENT = 15
DOCX_CAPTION_INDENT = 15
DOCX_REFERENCE_INDENT = 10
DOCX_METADATA_SPACER = 80
DOCX_INDEXED_INDENT = 15
DOCX_INDEXED_SPACE_AFTER = 8
DOCX_DEFAULT_IMAGE_SCALE_FACTOR = 0.6
DOCX_DEFAULT_PNG_RENDERING_FACTOR = 2.0

PDF_MAX_PAGE_BREAK_LEVEL = 4
PDF_MAX_TOC_LEVEL = 4
PDF_TOC_INDENT = 15
PDF_NORMAL_FONT = "Helvetica"
PDF_NORMAL_FONT_SIZE = 12
PDF_NORMAL_LEADING = 17
PDF_NORMAL_SPACE_BEFORE = 6
PDF_NORMAL_SPACE_AFTER = 6
PDF_TITLE_FONT_SIZE = 24
PDF_TITLE_LEADING = 30
PDF_TITLE_SPACE_AFTER = 15
PDF_CODE_FONT = "Courier"
PDF_CODE_FONT_SIZE = 11
PDF_CODE_LEADING = 12
PDF_CODE_INDENT = 10
PDF_SYNOPSIS_INDENT = 28
PDF_SYNOPSIS_SPACE_AFTER = 15
PDF_QUOTE_FONT = "Times-Roman"
PDF_QUOTE_FONT_SIZE = 11
PDF_QUOTE_LEADING = 14
PDF_QUOTE_SPACE_BEFORE = 6
PDF_QUOTE_INDENT = 28
PDF_FOOTNOTE_INDENT = 10
PDF_REFERENCE_SPACE_BEFORE = 7
PDF_REFERENCE_INDENT = 10
PDF_IMAGE_SPACE = 12
PDF_DEFAULT_IMAGE_SCALE_FACTOR = 0.6
PDF_DEFAULT_PNG_RENDERING_FACTOR = 2.0
