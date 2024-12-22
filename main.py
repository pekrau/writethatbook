"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import install

install()

import os

if "WRITETHATBOOK_DIR" not in os.environ:
    dirpath = "/tmp/writethatbook"
    if not os.path.exists(dirpath):
        os.mkdir(dirpath)
    os.environ["WRITETHATBOOK_DIR"] = dirpath
    print("WARNING: Env var WRITETHATBOOK_DIR is not defined.")
    print(f"         Using '{dirpath}' as fallback.")


from fasthtml.common import *

import auth
from books import Book, read_books, get_books, get_refs, get_dump_tgz_content
import components
import constants
from errors import *
import users
import utils
from utils import Tx
import book_app, edit_app, append_app, move_app, copy_app, delete_app, diff_app, meta_app, refs_app, search_app, state_app, user_app


app, rt = components.get_fast_app(
    routes=[
        Mount("/book", book_app.app),
        Mount("/edit", edit_app.app),
        Mount("/append", append_app.app),
        Mount("/move", move_app.app),
        Mount("/copy", copy_app.app),
        Mount("/delete", delete_app.app),
        Mount("/refs", refs_app.app),
        Mount("/meta", meta_app.app),
        Mount("/state", state_app.app),
        Mount("/search", search_app.app),
        Mount("/user", user_app.app),
        Mount("/diff", diff_app.app),
    ],
)


@rt("/")
def get(request):
    "Home page; list of books."
    auth.allow_anyone(request)

    actions = []
    if auth.authorized(request, *auth.book_create_rules):
        actions.append(["Create or upload book", "/book"])
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
        Main(book_app.get_books_table(request, get_books(request)), cls="container"),
        components.footer(request),
    )


@rt("/ping")
def get(request):
    "Health check of web app instance."
    auth.allow_anyone(request)
    return f"Hello, {auth.logged_in(request) or 'anonymous'}, from {constants.SOFTWARE} {constants.__version__}"


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

refs = get_refs()
if not refs.frontmatter.get("owner"):
    refs.frontmatter["owner"] = "system"
refs.write()

serve()
