"Information about system and state."

from icecream import ic

import sys

import bibtexparser
import docx
import fasthtml
from fasthtml.common import *
import fpdf
import marko
import psutil
import yaml

import auth
from books import Book, get_books, get_refs
import components
import constants
from errors import *
import users
import utils
from utils import Tx


app, rt = utils.get_fast_app()


@rt("/software")
def get(request):
    "View software versions."
    auth.allow_anyone(request)

    title = Tx("Software")
    menu = []
    if auth.is_admin(request):
        menu.append(A(Tx("State (JSON)"), href="/meta/state"))
        menu.append(A(Tx("System"), href="/meta/system"))
    rows = []
    for name, href, version in [(constants.SOFTWARE,
                                 "https://github.com/pekrau/mdbook",
                                 constants.__version__),
                                ("Python",
                                 "https://www.python.org/",
                                 f"{'.'.join([str(v) for v in sys.version_info[0:3]])}"),
                                ("fastHTML",
                                 "https://fastht.ml/",
                                 fasthtml.__version__),
                                ("Marko",
                                 "https://marko-py.readthedocs.io/",
                                 marko.__version__),
                                ("python-docx",
                                 "https://python-docx.readthedocs.io/en/latest/",
                                 docx.__version__),
                                ("fpdf2",
                                 "https://py-pdf.github.io/fpdf2/",
                                 fpdf.__version__),
                                ("PyYAML",
                                 "https://pypi.org/project/PyYAML/",
                                 yaml.__version__),
                                ("bibtexparser",
                                 "https://pypi.org/project/bibtexparser/",
                                 bibtexparser.__version__)]:
        rows.append(Tr(
            Td(
                A(name, href=href)
            ),
            Td(version),
        )
                    )
                                
    return (
        Title(title),
        components.header(request, title, menu=menu),
        Main(
            Table(
                Thead(
                    Tr(Th(Tx("Software")), Th(Tx("Version")))),
                Tbody(*rows),
            ),
            cls="container",
        ),
    )


@rt("/state")
def get(request):
    "Return JSON for the overall state of this site."
    auth.allow_admin(request)

    books = {}
    for book in get_books(request) + [get_refs()]:
        books[book.id] = dict(
            title=book.title,
            modified=utils.timestr(
                filepath=book.absfilepath, localtime=False, display=False
            ),
            n_items=len(book.all_items),
            sum_characters=book.frontmatter["sum_characters"],
            digest=book.frontmatter["digest"],
        )

    return dict(
        software=constants.SOFTWARE,
        version=constants.__version__,
        now=utils.timestr(localtime=False, display=False),
        books=books,
    )


@rt("/system")
def get(request):
    "View aggregate system information."
    auth.allow_admin(request)

    title = Tx("System")
    return (
        Title(title),
        components.header(request, title),
        Main(
            Table(
                Tr(
                    Td(Tx("Memory usage")),
                    Td(utils.thousands(psutil.Process().memory_info().rss), " bytes"),
                ),
            ),
            cls="container",
        ),
    )


@rt("/index/{book:Book}")
def get(request, book: Book):
    "Display the indexed terms of the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    items = []
    for key, texts in sorted(book.indexed.items(), key=lambda tu: tu[0].lower()):
        refs = []
        for text in sorted(texts, key=lambda t: t.ordinal):
            refs.append(
                Li(A(text.fulltitle, cls="secondary", href=f"/book/{book}/{text.path}"))
            )
        items.append(Li(key, Small(Ul(*refs))))

    title = Tx("Index")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(Ul(*items), cls="container"),
    )


@rt("/recent/{book:Book}")
def get(request, book: Book):
    "Display the most recently modified items in the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    items = sorted(book.all_items, key=lambda i: i.modified, reverse=True)
    items = items[: constants.MAX_RECENT]

    menu = []
    rows = [
        Tr(Td(A(i.fulltitle, href=f"/book/{id}/{i.path}")), Td(i.modified))
        for i in items
    ]

    title = Tx("Recently modified")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, menu=menu),
        Main(
            P(Table(Tbody(*rows))),
            cls="container",
        ),
    )


@rt("/info/{book:Book}")
def get(request, book: Book):
    "Display information about the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    segments = [H3(book.title)]
    if book.subtitle:
        segments.append(H4(book.subtitle))
    for author in book.authors:
        segments.append(H5(author))

    segments.append(
        Table(
            Tr(Th(Tx("Title")),
               Td(book.title)),
            Tr(Th(Tx("Type")),
               Td(Tx(book.type.capitalize()))),
            Tr(Th(Tx("Status")),
               Td(Tx(book.status))),
            Tr(Th(Tx("Owner")),
               Td(Tx(book.owner))),
            Tr(Th(Tx("Modified")),
               Td(Tx(book.modified))),
            Tr(Th(Tx("Words")),
               Td(Tx(utils.thousands(book.sum_words)))),
            Tr(Th(Tx("Characters")),
               Td(Tx(utils.thousands(book.sum_characters)))),
            Tr(Th(Tx("Language")),
               Td(Tx(book.frontmatter.get("language") or "-"))),
        )
    )

    menu = [
        A(f'{Tx("Edit")}', href=f"/edit/{book}"),
        # A(f'{Tx("Append")}', href=f"/append/{id}"),
        A(Tx("Status list"), href=f"/book/_status/{book}"),
        A(Tx("State (JSON)"), href=f"/book/_state/{book}"),
        A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/book/{book}.docx"),
        A(f'{Tx("Download")} {Tx("PDF file")}', href=f"/book/{book}.pdf"),
        A(f'{Tx("Download")} {Tx("TGZ file")}', href=f"/book/{book}.tgz"),
    ]

    title = Tx("Information")
    return (
        Title(title),
        components.header(request, title, book=book, menu=menu, status=book.status),
        Main(*segments, cls="container"),
    )


@rt("/status/{book:Book}")
def get(request, book: Book):
    "List each status and texts of the book in it."
    auth.authorize(request, *auth.book_view_rules, book=book)

    rows = [Tr(Th(Tx("Status"), Th(Tx("Texts"))))]
    for status in constants.STATUSES:
        texts = []
        for t in book.all_texts:
            if t.status == status:
                if texts:
                    texts.append(Br())
                texts.append(A(t.heading, href=f"/book/{id}/{t.path}"))
        rows.append(
            Tr(
                Td(
                    components.blank(0.5, f"background-color: {status.color};"),
                    components.blank(0.2),
                    Tx(str(status)),
                    valign="top",
                ),
                Td(*texts),
            )
        )

    title = Tx("Status list")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
        Main(Table(*rows), cls="container"),
    )


@rt("/state/{book:Book}")
def get(request, book: Book):
    "Get the state (JSON) for the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    result = dict(
        software=constants.SOFTWARE,
        version=constants.__version__,
        now=utils.timestr(localtime=False, display=False),
    )
    result.update(book.state)

    return result
