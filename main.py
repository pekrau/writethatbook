"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import ic

import io
from http import HTTPStatus as HTTP
import os
from pathlib import Path
import re
import tarfile

from fasthtml.common import *

import auth
from books import read_books, get_books, get_refs
import components
import constants
from errors import *
import users
import utils
from utils import Tx
import book_app, edit_app, append_app, mod_app, move_app, copy_app, delete_app, \
    meta_app, refs_app, search_app, user_app, sync_app


if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError("env var WRITETHATBOOK_DIR not defined: cannot execute")


app, rt = utils.get_fast_app(
    routes=[
        Mount("/book", book_app.app),
        Mount("/edit", edit_app.app),
        Mount("/append", append_app.app),
        Mount("/mod", mod_app.app),
        Mount("/move", move_app.app),
        Mount("/copy", copy_app.app),
        Mount("/delete", delete_app.app),
        Mount("/meta", meta_app.app),
        Mount("/refs", refs_app.app),
        Mount("/search", search_app.app),
        Mount("/user", user_app.app),
        Mount("/sync", sync_app.app),
    ],
)


@rt("/")
def get(request):
    "Home page; list of books."
    auth.allow_anyone(request)
    hrows = Tr(
        Th(Tx("Title")),
        Th(Tx("Type")),
        Th(Tx("Status")),
        Th(Tx("Characters")),
        Th(Tx("Owner")),
        Th(Tx("Modified")),
    )
    rows = []
    for book in get_books(request):
        user = users.get(book.owner)
        rows.append(
            Tr(
                Td(A(book.title, href=f"/book/{book.id}")),
                Td(Tx(book.frontmatter.get("type", constants.BOOK).capitalize())),
                Td(
                    Tx(
                        book.frontmatter.get(
                            "status", repr(constants.STARTED)
                        ).capitalize()
                    )
                ),
                Td(Tx(utils.thousands(book.frontmatter.get("sum_characters", 0)))),
                Td(user),
                # Td(user.name or user.id),
                Td(book.modified),
            )
        )
    user = auth.logged_in(request)
    actions = []
    if user:
        actions.append(["Create or upload book", "/book"])
    pages = [("References", "/refs")]
    if user:
        pages.append([f"User {user.name or user.id}", f"/user/view/{user.id}"])
    if auth.is_admin(request):
        pages.append(["All users", "/user/list"])
        pages.append(["State (JSON)", "/meta/state"])
        pages.append(["System", "/meta/system"])
        # if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
        #     menu.append(A(Tx("Differences"), href="/differences"))
        pages.append(["Download dump file", "/dump"])
    pages.append(["Software", "/meta/software"])

    title = Tx("Books")
    return (
        Title(title),
        components.header(request, title, actions=actions, pages=pages),
        Main(Table(Thead(*hrows), Tbody(*rows)), cls="container"),
    )


@rt("/ping")
def get(request):
    "Health check."
    auth.allow_anyone(request)
    return f"Hello, {request.scope.get('current_user') or 'anonymous'}!"


@rt("/dump")
def get(request):
    "Download a gzipped tar file of all data."
    auth.allow_admin(request)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tgzfile:
        for path in Path(os.environ["WRITETHATBOOK_DIR"]).iterdir():
            tgzfile.add(path, arcname=path.name, recursive=True)
    filename = f"writethatbook_{utils.timestr(safe=True)}.tgz"

    return Response(
        content=buffer.getvalue(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
read_books()

serve()
