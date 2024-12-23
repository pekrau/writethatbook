"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import install

install()

import os

if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError("Required environment variable WRITETHATBOOK_DIR is undefined.")


from fasthtml.common import *

import apps
import auth
from books import Book, read_books, get_books, get_refs, get_dump_tgz_content
import components
import constants
from errors import *
import users
import utils
from utils import Tx


app, rt = components.get_fast_app(routes=apps.routes)


@rt("/")
def get(request):
    "Home page; list of books."
    auth.allow_anyone(request)

    actions = []
    if auth.authorized(request, *auth.book_create_rules):
        actions.append(["Create or upload book", "/book"])
        actions.append(["Reread books", "/reread"])
    pages = [("References", "/refs")]
    if auth.is_admin(request):
        pages.append(["All users", "/user/list"])
        pages.append(["Download dump file", "/dump"])
        pages.append(["State (JSON)", "/state"])
        if auth.authorized(request, *auth.book_diff_rules):
            pages.append(["Differences", "/diff"])
        pages.append(["System", "/meta/system"])
    pages.append(["Software", "/meta/software"])

    title = Tx("Books")
    return (
        Title(title),
        components.header(request, title, actions=actions, pages=pages),
        Main(apps.book.get_books_table(request, get_books(request)), cls="container"),
        components.footer(request),
    )


@rt("/ping")
def get(request):
    "Health check of web app instance."
    auth.allow_anyone(request)
    return f"Hello, {auth.logged_in(request) or 'anonymous'}, from {constants.SOFTWARE} {constants.__version__}"


@rt("/reread")
def get(request):
    auth.allow_admin(request)
    read_books()
    return components.redirect("/")


@rt("/dump")
def get(request):
    "Download a gzipped tar file of all data."
    auth.allow_admin(request)

    filename = f"writethatbook_{utils.timestr(safe=True)}.tgz"
    return Response(
        content=get_dump_tgz_content(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
read_books()

serve()
