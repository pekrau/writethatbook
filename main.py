"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import ic

import io
from http import HTTPStatus as HTTP
import os
from pathlib import Path
import tarfile

from fasthtml.common import *

import auth
from books import read_books, get_books, get_refs
import book_app
import components
import constants
import edit_app
from errors import *
import meta_app
import mod_app
import refs_app
import users
import user_app
import utils
from utils import Tx


if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError("env var WRITETHATBOOK_DIR not defined: cannot execute")


app, rt = utils.get_fast_app(
    routes=[
        Mount("/book", book_app.app),
        Mount("/edit", edit_app.app),
        Mount("/mod", mod_app.app),
        Mount("/meta", meta_app.app),
        Mount("/refs", refs_app.app),
        Mount("/user", user_app.app),
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
        actions.append(["Download dump file", "/dump"])
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


# @rt("/references/upload")
# def get():
#     "Upload a gzipped tar file of references; replace any reference with the same name."
#     title = Tx("Upload references")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 Input(type="file", name="tgzfile"),
#                 Button(f'{Tx("Upload")} {Tx("TGZ file")}'),
#                 action="/references/upload",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/references/upload")
# async def post(tgzfile: UploadFile):
#     "Actually add or replace references by contents of the uploaded file."
#     utils.unpack_tgzfile(
#         Path(os.environ["WRITETHATBOOK_DIR"]) / constants.REFSS,
#         await tgzfile.read(),
#         references=True,
#     )
#     books.get_references(reread=True)

#     return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)


# @rt("/search/{id:str}")
# def post(id: str, form: dict):
#     "Actually search the book for a given term."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
#     term = form.get("term")
#     if term:
#         items = [
#             Li(A(i.fulltitle, href=f"/book/{id}/{i.path}"))
#             for i in sorted(
#                 book.search(
#                     utils.wildcard_to_regexp(term), ignorecase=term == term.lower()
#                 ),
#                 key=lambda i: i.ordinal,
#             )
#         ]
#         if items:
#             result = P(Ul(*items))
#         else:
#             result = P(f'{Tx("No result")}.')
#     else:
#         result = P()

#     menu = [components.index_link(book)]
#     if id != constants.REFSS:
#         menu.append(components.refs_link())

#     title = f'{Tx("Search")} {Tx("book")}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status, menu=menu),
#         Main(
#             components.search_form(f"/search/{id}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/search/{id:str}/{path:path}")
# def post(id: str, path: str, form: dict):
#     "Actually search the item (text or section)  for a given term."
#     book = books.get_book(id)
#     item = book[path]
#     term = form.get("term")
#     if term:
#         items = [
#             Li(A(i.fulltitle, href=i.path))
#             for i in sorted(
#                 item.search(
#                     utils.wildcard_to_regexp(term), ignorecase=term == term.lower()
#                 ),
#                 key=lambda i: i.ordinal,
#             )
#         ]
#         if items:
#             result = P(Ul(*items))
#         else:
#             result = P(f'{Tx("No result")}.')
#     else:
#         result = P()

#     title = f"{Tx('Search')} '{item.fulltitle}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=item.status),
#         Main(
#             components.search_form(f"/search/{id}/{path}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/differences")
# def get():
#     "Compare this local site with the update site."
#     try:
#         remote = utils.get_state_remote()
#     except ValueError as message:
#         raise Error(message, HTTP.INTERNAL_SERVER_ERROR)
#     state = books.get_state()
#     rows = []
#     here_books = state["books"].copy()
#     for id, rbook in remote["books"].items():
#         rurl = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}"
#         lbook = here_books.pop(id, {})
#         title = lbook.get("title") or rbook.get("title")
#         if lbook:
#             if lbook["digest"] == rbook["digest"]:
#                 action = Tx("Identical")
#             else:
#                 action = A(Tx("Differences"), href=f"/differences/{id}", role="button")
#             rows.append(
#                 Tr(
#                     Th(Strong(title), scope="row"),
#                     Td(
#                         A(rurl, href=rurl),
#                         Br(),
#                         utils.tolocaltime(rbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(rbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td(
#                         A(id, href=f"/book/{id}"),
#                         Br(),
#                         utils.tolocaltime(lbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(lbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td(action),
#                 ),
#             )
#         else:
#             rows.append(
#                 Tr(
#                     Th(Strong(title), scope="row"),
#                     Td(
#                         A(rurl, href=rurl),
#                         Br(),
#                         utils.tolocaltime(rbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(rbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td("-"),
#                     Td(
#                         Form(
#                             Button(Tx("Update here"), type="submit"),
#                             method="post",
#                             action=f"/pull/{id}",
#                         )
#                     ),
#                 )
#             )
#     for id, lbook in here_books.items():
#         rows.append(
#             Tr(
#                 Th(Strong(lbook.get("title") or rbook.get("title")), scope="row"),
#                 Td("-"),
#                 Td(
#                     A(id, href=f"/book/{id}"),
#                     Br(),
#                     utils.tolocaltime(lbook["modified"]),
#                     Br(),
#                     f'{utils.thousands(lbook["sum_characters"])} {Tx("characters")}',
#                 ),
#                 Td(A(Tx("Differences"), href=f"/differences/{id}", role="button")),
#             ),
#         )

#     title = Tx("Differences")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Table(
#                 Thead(
#                     Tr(
#                         Th(Tx("Book")),
#                         Th(os.environ["WRITETHATBOOK_UPDATE_SITE"], scope="col"),
#                         Th(Tx("Here"), scope="col"),
#                         Th(scope="col"),
#                     ),
#                 ),
#                 Tbody(*rows),
#             ),
#             cls="container",
#         ),
#     )


# @rt("/differences/{id:str}")
# def get(id: str):
#     "Compare this local book with the update site book. One of them may not exist."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     try:
#         remote = utils.get_state_remote(id)
#     except ValueError as message:
#         raise Error(message, HTTP.INTERNAL_SERVER_ERROR)
#     if id == constants.REFSS:
#         book = books.get_references()
#         here = book.state
#     else:
#         try:
#             book = books.get_book(id)
#             here = book.state
#         except Error:
#             here = {}
#     rurl = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}"
#     lurl = f"/book/{id}"

#     rows, rflag, lflag = items_diffs(
#         remote.get("items", []), rurl, here.get("items", []), lurl
#     )

#     # The book 'index.md' files may differ, if they exist.
#     if remote and here:
#         row, rf, lf = item_diff(
#             remote,
#             os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}",
#             here,
#             f"/book/{id}",
#         )
#         if row:
#             rows.insert(0, row)
#             rflag += rf
#             lflag += lf

#     title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
#     if not rows:
#         if not remote:
#             segments = (
#                 H4(f'{Tx("Not present in")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}'),
#                 Form(
#                     Button(f'{Tx("Update")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}'),
#                     action=f"/push/{id}",
#                     method="post",
#                 ),
#             )
#         elif not here:
#             segments = (
#                 H4(Tx("Not present here")),
#                 Form(
#                     Button(Tx("Update here")),
#                     action=f"/pull/{id}",
#                     method="post",
#                 ),
#             )
#         else:
#             segments = (
#                 H4(Tx("Identical")),
#                 Div(
#                     Div(Strong(A(rurl, href=rurl))),
#                     Div(Strong(A(id, href=lurl))),
#                     cls="grid",
#                 ),
#             )

#         return (
#             Title(title),
#             components.header(request, title, book=book),
#             Main(*segments, cls="container"),
#         )

#     rows.append(
#         Tr(
#             Td(),
#             Td(
#                 Form(
#                     Button(
#                         f'{Tx("Update")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}',
#                         cls=None if rflag else "outline",
#                     ),
#                     action=f"/push/{id}",
#                     method="post",
#                 )
#             ),
#             Td(
#                 Form(
#                     Button(Tx("Update here"), cls=None if lflag else "outline"),
#                     action=f"/pull/{id}",
#                     method="post",
#                 ),
#                 colspan=3,
#             ),
#         )
#     )

#     title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Table(
#                 Thead(
#                     Tr(
#                         Th(),
#                         Th(A(rurl, href=rurl), colspan=1, scope="col"),
#                         Th(A(id, href=lurl), colspan=3, scope="col"),
#                     ),
#                     Tr(
#                         Th(Tx("Title"), scope="col"),
#                         Th(),
#                         Th(Tx("Age"), scope="col"),
#                         Th(Tx("Size"), scope="col"),
#                         Th(),
#                     ),
#                 ),
#                 Tbody(*rows),
#             ),
#             cls="container",
#         ),
#     )


# def items_diffs(ritems, rurl, litems, lurl):
#     """Return list of rows and flags specifying differences between
#     remote and local items.
#     """
#     result = []
#     rflag = 0
#     lflag = 0
#     for ritem in ritems:
#         riurl = f'{rurl}/{ritem["name"]}'
#         for pos, litem in enumerate(list(litems)):
#             if litem["title"] != ritem["title"]:
#                 continue
#             liurl = f'{lurl}/{litem["name"]}'
#             row, rf, lf = item_diff(ritem, riurl, litem, liurl)
#             rflag += rf
#             lflag += lf
#             if row:
#                 result.append(row)
#             litems.pop(pos)
#             try:
#                 rows, rf, lf = items_diffs(ritem["items"], riurl, litem["items"], liurl)
#                 rflag += rf
#                 lflag += lf
#                 result.extend(rows)
#             except KeyError as message:
#                 pass
#             break
#         else:
#             row, rf, lf = item_diff(ritem, riurl, None, None)
#             rflag += rf
#             lflag += lf
#             result.append(row)
#     for litem in litems:
#         row, rf, lf = item_diff(None, None, litem, f'{lurl}/{litem["name"]}')
#         rflag += rf
#         lflag += lf
#         result.append(row)
#     return result, rflag, lflag


# def item_diff(ritem, riurl, litem, liurl):
#     "Return row and update flags specifying differences between the items."
#     if ritem is None:
#         return (
#             Tr(
#                 Td(Strong(litem["title"])),
#                 Td("-"),
#                 Td("-"),
#                 Td("-"),
#                 Td(A(liurl, href=liurl)),
#             ),
#             1,
#             0,
#         )
#     elif litem is None:
#         return (
#             Tr(
#                 Td(Strong(ritem["title"])),
#                 Td(A(riurl, href=riurl)),
#                 Td("-"),
#                 Td("-"),
#                 Td("-"),
#             ),
#             0,
#             1,
#         )
#     if litem["digest"] == ritem["digest"]:
#         return None, 0, 0
#     if litem["modified"] < ritem["modified"]:
#         age = "Older"
#         rflag = 0
#         lflag = 1
#     elif litem["modified"] > ritem["modified"]:
#         age = "Newer"
#         rflag = 1
#         lflag = 0
#     else:
#         age = "Same"
#         rflag = 0
#         lflag = 0
#     if litem["n_characters"] < ritem["n_characters"]:
#         size = "Smaller"
#     elif litem["n_characters"] > ritem["n_characters"]:
#         size = "Larger"
#     else:
#         size = "Same"
#     return (
#         Tr(
#             Td(Strong(ritem["title"])),
#             Td(A(riurl, href=riurl)),
#             Td(Tx(age)),
#             Td(Tx(size)),
#             Td(A(liurl, href=liurl)),
#         ),
#         rflag,
#         lflag,
#     )


# @rt("/pull/{id:str}")
# def post(id: str):
#     "Update book at this site by downloading it from the remote site."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)

#     url = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/tgz/{id}"
#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     headers = dict(apikey=os.environ["WRITETHATBOOK_UPDATE_APIKEY"])

#     response = requests.get(url, headers=headers)

#     if response.status_code != HTTP.OK:
#         raise Error(f"remote error: {response.content}", HTTP.BAD_REQUEST)
#     if response.headers["Content-Type"] != constants.GZIP_MIMETYPE:
#         raise Error("invalid file type from remote", HTTP.BAD_REQUEST)
#     content = response.content
#     if not content:
#         raise Error("empty TGZ file from remote", HTTP.BAD_REQUEST)

#     # Temporarily save old contents.
#     if dirpath.exists():
#         saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
#         dirpath.replace(saved_dirpath)
#     else:
#         saved_dirpath = None
#     try:
#         utils.unpack_tgzfile(dirpath, content, references=id == constants.REFSS)
#     except ValueError as message:
#         # If failure, reinstate saved contents.
#         if saved_dirpath:
#             saved_dirpath.replace(dirpath)
#         raise Error(f"error reading TGZ file from remote: {message}", HTTP.BAD_REQUEST)
#     else:
#         # Remove saved contents after new was successful unpacked.
#         if saved_dirpath:
#             shutil.rmtree(saved_dirpath)

#     if id == constants.REFSS:
#         books.get_references(reread=True)
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)
#     else:
#         books.get_book(id, reread=True)
#         return RedirectResponse(f"/book/{id}", status_code=HTTP.SEE_OTHER)


# @rt("/push/{id:str}")
# def post(id: str):
#     "Update book at the remote site by uploading it from this site."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     url = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/receive/{id}"
#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     tgzfile = utils.get_tgzfile(dirpath)
#     tgzfile.seek(0)
#     headers = dict(apikey=os.environ["WRITETHATBOOK_UPDATE_APIKEY"])
#     response = requests.post(
#         url,
#         headers=headers,
#         files=dict(tgzfile=("tgzfile", tgzfile, constants.GZIP_MIMETYPE)),
#     )
#     if response.status_code != HTTP.OK:
#         error(f"remote did not accept push: {response.content}", HTTP.BAD_REQUEST)
#     return RedirectResponse("/", status_code=HTTP.SEE_OTHER)


# @rt("/receive/{id:str}")
# async def post(id: str, tgzfile: UploadFile = None):
#     "Update book at this site by another site uploading it."
#     if not id:
#         raise Error("book id may not be empty", HTTP.BAD_REQUEST)
#     if id.startswith("_"):
#         raise Error("book id may not start with an underscore '_'", HTTP.BAD_REQUEST)

#     content = await tgzfile.read()
#     if not content:
#         raise Error("no content in TGZ file", HTTP.BAD_REQUEST)

#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     if dirpath.exists():
#         # Temporarily save old contents.
#         saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
#         dirpath.rename(saved_dirpath)
#     else:
#         saved_dirpath = None
#     try:
#         utils.unpack_tgzfile(dirpath, content)
#         if saved_dirpath:
#             shutil.rmtree(saved_dirpath)
#     except ValueError as message:
#         if saved_dirpath:
#             saved_dirpath.rename(dirpath)
#         raise Error(f"error reading TGZ file: {message}", HTTP.BAD_REQUEST)

#     if id == constants.REFS:
#         books.get_references(reread=True)
#     else:
#         books.get_book(id, reread=True)
#     return "success"


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
read_books()

serve()
