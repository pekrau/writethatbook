"Pages for information about system and state."

import os
import shutil
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


app, rt = components.get_fast_app()


@rt("/software")
def get(request):
    "View software versions."
    auth.allow_anyone(request)

    title = Tx("Software")
    pages = [("References", "/refs")]
    if auth.is_admin(request):
        pages.append(["State (JSON)", "/state"])
        pages.append(["System", "/meta/system"])
    rows = []
    for name, href, version in [
        (constants.SOFTWARE, "https://github.com/pekrau/mdbook", constants.__version__),
        (
            "Python",
            "https://www.python.org/",
            f"{'.'.join([str(v) for v in sys.version_info[0:3]])}",
        ),
        ("fastHTML", "https://fastht.ml/", fasthtml.__version__),
        ("Marko", "https://marko-py.readthedocs.io/", marko.__version__),
        (
            "python-docx",
            "https://python-docx.readthedocs.io/en/latest/",
            docx.__version__,
        ),
        ("fpdf2", "https://py-pdf.github.io/fpdf2/", fpdf.__version__),
        ("PyYAML", "https://pypi.org/project/PyYAML/", yaml.__version__),
        (
            "bibtexparser",
            "https://pypi.org/project/bibtexparser/",
            bibtexparser.__version__,
        ),
    ]:
        rows.append(
            Tr(
                Td(A(name, href=href)),
                Td(version),
            )
        )

    return (
        Title(title),
        components.header(request, title, pages=pages),
        Main(
            Table(
                Thead(Tr(Th(Tx("Software")), Th(Tx("Version")))),
                Tbody(*rows),
            ),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/system")
def get(request):
    "View aggregate system information."
    auth.allow_admin(request)

    disk_usage = shutil.disk_usage(os.environ["WRITETHATBOOK_DIR"])
    dir_size = 0
    for dirpath, dirnames, filenames in os.walk(os.environ["WRITETHATBOOK_DIR"]):
        dp = Path(dirpath)
        for filename in filenames:
            fp = dp / filename
            dir_size += os.path.getsize(fp)

    pages = [
        ("References", "/refs"),
        ("All users", "/user/list"),
        ("State (JSON)", "/state"),
        ("Software", "/meta/software"),
    ]

    if os.environ.get("WRITETHATBOOK_REMOTE_SITE"):
        remote = A(
            os.environ.get("WRITETHATBOOK_REMOTE_SITE"),
            href=os.environ.get("WRITETHATBOOK_REMOTE_SITE"),
        )
    else:
        remote = "-"
    title = Tx("System")
    return (
        Title(title),
        components.header(request, title, pages=pages),
        Main(
            Table(
                Tr(
                    Td(Tx("Remote site")),
                    Td(remote),
                ),
                Tr(
                    Td(Tx("RAM usage")),
                    Td(
                        components.thousands(psutil.Process().memory_info().rss),
                        " bytes",
                    ),
                ),
                Tr(
                    Td(Tx("Data size")),
                    Td(components.thousands(dir_size), " bytes"),
                ),
                Tr(
                    Td(Tx("Disk free")),
                    Td(components.thousands(disk_usage.free), " bytes"),
                ),
                Tr(
                    Td(Tx("# users")),
                    Td(str(len(users.database))),
                ),
                Tr(
                    Td(Tx("# books")),
                    Td(str(len(get_books(request)))),
                ),
            ),
            cls="container",
        ),
        components.footer(request),
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
        items.append(Li(key, Small(Ul(*refs)), id=key))

    pages = [
        ("References", "/refs"),
        ("Recently modified", f"/meta/recent/{book}"),
        ("Status list", f"/meta/status/{book}"),
        ("Information", f"/meta/info/{book}"),
        ("State (JSON)", f"/state/{book}"),
        ("Download DOCX file", f"/book/{book}.docx"),
        ("Download PDF file", f"/book/{book}.pdf"),
        ("Download TGZ file", f"/book/{book}.tgz"),
    ]
    if auth.authorized(request, *auth.book_diff_rules, book=book):
        pages.append(("Differences", f"/diff/{book}"))

    title = Tx("Index")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, pages=pages),
        Main(Ul(*items), cls="container"),
        components.footer(request),
    )


@rt("/recent/{book:Book}")
def get(request, book: Book):
    "Display the most recently modified items in the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    items = sorted(list(book), key=lambda i: i.modified, reverse=True)
    items = items[: constants.MAX_RECENT]

    rows = [
        Tr(Td(A(i.fulltitle, href=f"/book/{book}/{i.path}")), Td(i.modified))
        for i in items
    ]

    pages = [
        ("References", "/refs"),
        ("Index", f"/meta/index/{book}"),
        ("Status list", f"/meta/status/{book}"),
        ("State (JSON)", f"/state/{book}"),
        ("Download DOCX file", f"/book/{book}.docx"),
        ("Download PDF file", f"/book/{book}.pdf"),
        ("Download TGZ file", f"/book/{book}.tgz"),
    ]
    if auth.authorized(request, *auth.book_diff_rules, book=book):
        pages.append(("Differences", f"/diff/{book}"))

    title = Tx("Recently modified")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, pages=pages),
        Main(
            P(Table(Tbody(*rows))),
            cls="container",
        ),
        components.footer(request),
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

    owner = users.get(book.owner)
    if auth.authorized(request, *auth.user_view_rules, user=owner):
        owner = A(owner.name or owner.id, href=f"/user/view/{owner}")
    else:
        owner = owner.name or owner.id
    segments.append(
        Table(
            Tr(Th(Tx("Title")), Td(book.title)),
            Tr(Th(Tx("Type")), Td(Tx(book.type.capitalize()))),
            Tr(Th(Tx("Status")), Td(Tx(book.status))),
            Tr(Th(Tx("Owner")), Td(owner)),
            Tr(Th(Tx("Modified")), Td(Tx(book.modified))),
            Tr(Th(Tx("Words")), Td(Tx(components.thousands(book.sum_words)))),
            Tr(Th(Tx("Characters")), Td(components.thousands(book.sum_characters))),
            Tr(Th(Tx("Language")), Td(Tx(book.frontmatter.get("language") or "-"))),
        )
    )

    pages = [
        ("References", "/refs"),
        ("Index", f"/meta/index/{book}"),
        ("Recently modified", f"/meta/recent/{book}"),
        ("Status list", f"/meta/status/{book}"),
        ("State (JSON)", f"/state/{book}"),
        ("Download DOCX file", f"/book/{book}.docx"),
        ("Download PDF file", f"/book/{book}.pdf"),
        ("Download TGZ file", f"/book/{book}.tgz"),
    ]
    if auth.authorized(request, *auth.book_diff_rules, book=book):
        pages.append(("Differences", f"/diff/{book}"))

    title = Tx("Information")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, pages=pages),
        Main(*segments, cls="container"),
        components.footer(request),
    )


@rt("/status/{book:Book}")
def get(request, book: Book):
    "List each status and texts of the book in it."
    auth.authorize(request, *auth.book_view_rules, book=book)

    rows = [Tr(Th(Tx("Status"), Th(Tx("Texts"))))]
    for status in constants.STATUSES:
        texts = []
        for item in book:
            if item.is_text and item.status == status:
                if texts:
                    texts.append(Br())
                texts.append(A(item.heading, href=f"/book/{book}/{item.path}"))
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

    pages = [
        ("References", "/refs"),
        ("Index", f"/meta/index/{book}"),
        ("Recently modified", f"/meta/recent/{book}"),
        ("Information", f"/meta/info/{book}"),
        ("State (JSON)", f"/state/{book}"),
        ("Download DOCX file", f"/book/{book}.docx"),
        ("Download PDF file", f"/book/{book}.pdf"),
        ("Download TGZ file", f"/book/{book}.tgz"),
    ]
    if auth.authorized(request, *auth.book_diff_rules, book=book):
        pages.append(("Differences", f"/diff/{book}"))

    title = Tx("Status list")
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, pages=pages),
        Main(Table(*rows), cls="container"),
        components.footer(request),
    )
