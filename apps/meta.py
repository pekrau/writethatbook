"Pages for information about system and contents."

import os
import shutil
import sys

import bibtexparser
import docx
import fasthtml
from fasthtml.common import *
import marko
import psutil
import yaml
import reportlab

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
    rows = []
    for name, href, version in [
        (
            constants.SOFTWARE,
            "https://github.com/pekrau/writethatbook",
            constants.__version__,
        ),
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
        ("ReportLab", "https://docs.reportlab.com/", reportlab.__version__),
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
        components.header(request, title),
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
        components.header(request, title),
        Main(
            Table(
                Tr(
                    Td(Tx("Remote site")),
                    Td(remote),
                ),
                Tr(
                    Td(Tx("RAM usage")),
                    Td(
                        utils.thousands(psutil.Process().memory_info().rss),
                        " bytes",
                    ),
                ),
                Tr(
                    Td(Tx("Data size")),
                    Td(utils.thousands(dir_size), " bytes"),
                ),
                Tr(
                    Td(Tx("Disk free")),
                    Td(utils.thousands(disk_usage.free), " bytes"),
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
    auth.authorize(request, *auth.book_view, book=book)

    items = []
    for key, texts in sorted(book.indexed.items(), key=lambda tu: tu[0].lower()):
        refs = []
        for text in sorted(texts, key=lambda t: t.ordinal):
            refs.append(
                Li(
                    A(
                        text.fullheading,
                        cls="secondary",
                        href=f"/book/{book}/{text.path}",
                    )
                )
            )
        items.append(Li(key, Small(Ul(*refs)), id=key))

    title = Tx("Index")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(Ul(*items), cls="container"),
        components.footer(request),
    )


@rt("/recent/{book:Book}")
def get(request, book: Book):
    "Display the most recently modified items in the book."
    auth.authorize(request, *auth.book_view, book=book)

    items = sorted(list(book), key=lambda i: i.modified, reverse=True)
    items = items[: constants.MAX_RECENT]

    rows = [
        Tr(
            Td(A(i.fullheading, href=f"/book/{book}/{i.path}")),
            Td(utils.str_datetime_display(i.modified)),
        )
        for i in items
    ]

    title = Tx("Recently modified")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            P(Table(Tbody(*rows))),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/info/{book:Book}")
def get(request, book: Book):
    "Display information about the book."
    auth.authorize(request, *auth.book_view, book=book)

    segments = [H3(book.title)]
    if book.subtitle:
        segments.append(H4(book.subtitle))
    for author in book.authors:
        segments.append(H5(author))

    owner = users.get(book.owner)
    if auth.authorized(request, *auth.user_view, user=owner):
        owner = A(owner.name or owner.id, href=f"/user/view/{owner}")
    else:
        owner = owner.name or owner.id
    segments.append(
        Table(
            Tr(Th(Tx("Title")), Td(book.title)),
            Tr(Th(Tx("Type")), Td(Tx(book.type.capitalize()))),
            Tr(Th(Tx("Status")), Td(Tx(book.status))),
            Tr(Th(Tx("Owner")), Td(owner)),
            Tr(Th(Tx("Modified")), Td(utils.str_datetime_display(book.modified))),
            Tr(Th(Tx("Words")), Td(Tx(utils.thousands(book.sum_words)))),
            Tr(Th(Tx("Characters")), Td(utils.thousands(book.sum_characters))),
            Tr(Th(Tx("Language")), Td(Tx(book.frontmatter.get("language") or "-"))),
        )
    )

    title = Tx("Information")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(*segments, cls="container"),
        components.footer(request),
    )


@rt("/status/{book:Book}")
def get(request, book: Book):
    "List each status and texts of the book in it."
    auth.authorize(request, *auth.book_view, book=book)

    rows = [
        Tr(
            Th(
                Tx("Status"),
                Th(Tx("Texts")),
                Th(Tx("Words"), cls="right"),
                Th(Tx("Characters"), cls="right"),
            )
        )
    ]
    for status in constants.STATUSES:
        texts = [i for i in book if i.is_text and i.status == status]
        cells = [
            Td(
                components.blank(0.5, f"background-color: {status.color};"),
                components.blank(0.2),
                Tx(str(status)),
                rowspan=max(1, len(texts)),
                valign="top",
            )
        ]
        if len(texts) == 0:
            cells.append(Td("-", colspan=3))
            rows.append(Tr(cls="noborder", *cells))
        else:
            text = texts[0]
            cells.extend(
                [
                    Td(A(text.heading, href=f"/book/{book}/{text.path}")),
                    Td(str(text.sum_words), cls="right"),
                    Td(str(text.sum_characters), cls="right"),
                ]
            )
            rows.append(Tr(cls="noborder", *cells))
            for text in texts[1:]:
                rows.append(
                    Tr(
                        Td(A(text.heading, href=f"/book/{book}/{text.path}")),
                        Td(str(text.sum_words), cls="right"),
                        Td(str(text.sum_characters), cls="right"),
                        cls="noborder",
                    )
                )
    title = Tx("Status list")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(Table(cls="striped", *rows), cls="container"),
        components.footer(request),
    )
