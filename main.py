"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import install

install()

import io
import os
import tarfile

if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError(
        "Environment variable WRITETHATBOOK_DIR is undefined; it is required!"
    )


from fasthtml.common import *

import apps
import auth
import books
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

    tools = []
    if auth.authorized(request, *auth.book_create_rules):
        tools.append(["Create or upload book", "/book"])
        tools.append(["Reread books", "/reread"])
    if auth.authorized(request, *auth.book_diff_rules):
        tools.append(["Differences", f"/diff"])

    title = Tx("Books")
    return (
        Title(title),
        components.header(request, title, tools=tools),
        Main(
            apps.book.get_books_table(request, books.get_books(request)),
            cls="container",
        ),
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
    books.read_books()
    return components.redirect("/")


@rt("/reread/{book:Book}")
def get(request, book: books.Book, path: str = None):
    # Do not allow anyone to burden the server with reread.
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book = books.get_book(book.id, reread=True)
    href = f"/book/{book}"
    if path:
        href += "/" + path
    return components.redirect(href)


@rt("/dump")
def get(request):
    "Download a gzipped tar file of all data."
    auth.allow_admin(request)

    filename = f"writethatbook_{utils.str_datetime_safe()}.tgz"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tgzfile:
        for path in Path(os.environ["WRITETHATBOOK_DIR"]).iterdir():
            tgzfile.add(path, arcname=path.name, recursive=True)

    return Response(
        content=buffer.getvalue(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
books.read_books()

serve()
