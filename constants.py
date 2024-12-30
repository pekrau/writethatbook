"Constants."

import functools
from pathlib import Path

SOFTWARE = "WriteThatBook"
VERSION = (1, 6, 4)
__version__ = ".".join([str(n) for n in VERSION])


LANGUAGE_CODES = ("sv-SE", "en-GB", "en-US")
ENCODING = "utf-8"

MARKDOWN_EXT = ".md"
SOURCE_DIRPATH = Path(__file__).parent
FONT_DIRPATH = SOURCE_DIRPATH / "freefont"
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


STARTED = Status("started", 0, "gray")
OUTLINE = Status("outline", 1, "goldenrod")
DRAFT = Status("draft", 2, "darkorange")
MANUSCRIPT = Status("manuscript", 3, "crimson")
REVISED = Status("revised", 4, "blue")
DONE = Status("done", 5, "forestgreen")
FINAL = Status("final", 6, "black")
STATUSES = (STARTED, OUTLINE, DRAFT, MANUSCRIPT, REVISED, DONE, FINAL)
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

BOLD = "bold"
ITALIC = "italic"
NORMAL = "normal"
UNDERLINE = "underline"

CODE_STYLE = "mdbook Code"
CODE_FONT = "FreeMono"
CODE_LEFT_INDENT = 30

QUOTE_STYLE = "mdbook Quote"
QUOTE_FONT = "FreeSerif"
QUOTE_FONT_SIZE = 14
QUOTE_LEFT_INDENT = 30
QUOTE_RIGHT_INDENT = 70

FONT = "FreeSans"
FONT_NORMAL_SIZE = 12
FONT_LARGE_SIZE = FONT_NORMAL_SIZE + 2
FONT_TITLE_SIZE = 28
FONT_NORMAL = (FONT, FONT_NORMAL_SIZE)
FONT_ITALIC = (FONT, FONT_NORMAL_SIZE, ITALIC)
FONT_BOLD = (FONT, FONT_NORMAL_SIZE, BOLD)
FONT_LARGE_BOLD = (FONT, FONT_LARGE_SIZE, BOLD)
FONT_SMALL_SIZE = FONT_NORMAL_SIZE - 2
FONT_SMALL = (FONT, FONT_SMALL_SIZE)

NORMAL = "normal"
ITALIC = "italic"
BOLD = "bold"
UNDERLINE = "underline"
FONT_STYLES = (NORMAL, ITALIC, BOLD, UNDERLINE)

H1 = dict(
    tag="h1",
    font=(FONT, FONT_LARGE_SIZE + 10, BOLD),
    left_margin=40,
    spacing=30,
)
H2 = dict(
    tag="h2",
    font=(FONT, FONT_LARGE_SIZE + 5, BOLD),
    left_margin=30,
    spacing=20,
)
H3 = dict(
    tag="h3",
    font=(FONT, FONT_LARGE_SIZE + 3, BOLD),
    left_margin=20,
    spacing=15,
)
H4 = dict(
    tag="h4",
    font=(FONT, FONT_NORMAL_SIZE, BOLD),
    left_margin=15,
    spacing=10,
)
H5 = dict(
    tag="h5",
    font=(FONT, FONT_NORMAL_SIZE, BOLD),
    left_margin=10,
    spacing=5,
)
H6 = dict(
    tag="h6",
    font=(FONT, FONT_NORMAL_SIZE),
    left_margin=10,
    spacing=5,
)
H_LOOKUP = dict([(1, H1), (2, H2), (3, H3), (4, H4), (5, H5), (6, H6)])
MAX_H_LEVEL = max(H_LOOKUP)

FOOTNOTES_EACH_TEXT = "after each text"
FOOTNOTES_EACH_CHAPTER = "after each chapter"
FOOTNOTES_END_OF_BOOK = "at end of book"
FOOTNOTES_LOCATIONS = (
    FOOTNOTES_EACH_TEXT,
    FOOTNOTES_EACH_CHAPTER,
    FOOTNOTES_END_OF_BOOK,
)

DOCX_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MIMETYPE = "application/pdf"
GZIP_MIMETYPE = "application/gzip"

PDF_HREF_COLOR = (20, 20, 255)
PDF_LIST_INDENT = 30
PDF_THEMATIC_BREAK_INDENT = 100

PDF_PAGE_NUMBER = "page number"
PDF_TEXT_FULLTITLE = "text fulltitle"
PDF_TEXT_HEADING = "text heading"

PDF_INDEXED_XREF_DISPLAY = (
    PDF_PAGE_NUMBER,
    PDF_TEXT_FULLTITLE,
    PDF_TEXT_HEADING,
)
