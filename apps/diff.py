"Find and remedy differences in content between local site and remote site."

import datetime
import os
from pathlib import Path
import shutil

from fasthtml.common import *
import requests

import auth
from books import get_refs, get_book, unpack_tgz_content
import components
import constants
from errors import *
import utils
from utils import Tx


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Compare local site with the remote site. References are excluded."
    auth.authorize(request, *auth.book_diff)

    remote_state = get_remote_state()
    if not remote_state:
        raise Error("No response from remote site.", HTTP.INTERNAL_SERVER_ERROR)
    remote_books = remote_state["books"]

    import apps.state

    local_books = apps.state.get_books_state(request)

    rows = []
    for id, rbook in remote_books.items():
        if id == constants.REFS:
            lurl = "/refs"
            rurl = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/refs"
        else:
            lurl = f"/book/{id}"
            rurl = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/book/{id}"
        lbook = local_books.pop(id, {})
        if id == constants.REFS:
            title = Tx("References")
        else:
            title = lbook.get("title") or rbook.get("title")
        if lbook:
            if lbook["digest"] == rbook["digest"]:
                action = Tx("Identical")
            else:
                action = A(Tx("Differences"), href=f"/diff/{id}", role="button")
            rows.append(
                Tr(
                    Th(Strong(title), scope="row"),
                    Td(
                        A(rurl, href=rurl),
                        Br(),
                        utils.str_datetime_display(
                            datetime.datetime.fromisoformat(rbook["modified"])
                        ),
                        Br(),
                        f'{utils.numerical(rbook["sum_characters"])} {Tx("characters")}',
                    ),
                    Td(
                        A(lurl, href=lurl),
                        Br(),
                        utils.str_datetime_display(
                            datetime.datetime.fromisoformat(lbook["modified"])
                        ),
                        Br(),
                        f'{utils.numerical(lbook["sum_characters"])} {Tx("characters")}',
                    ),
                    Td(action),
                ),
            )
        else:
            rows.append(
                Tr(
                    Th(Strong(title), scope="row"),
                    Td(
                        A(rurl, href=rurl),
                        Br(),
                        utils.str_datetime_display(
                            datetime.datetime.fromisoformat(rbook["modified"])
                        ),
                        Br(),
                        f'{utils.numerical(rbook["sum_characters"])} {Tx("characters")}',
                    ),
                    Td("-"),
                    Td(
                        Form(
                            Button(Tx("Update here")),
                            method="post",
                            action=f"/diff/pull/{id}",
                        )
                    ),
                )
            )
    for id, lbook in local_books.items():
        rows.append(
            Tr(
                Th(Strong(lbook.get("title") or rbook.get("title")), scope="row"),
                Td("-"),
                Td(
                    A(id, href=f"/book/{id}"),
                    Br(),
                    utils.str_datetime_display(
                        datetime.datetime.fromisoformat(lbook["modified"])
                    ),
                    Br(),
                    f'{utils.numerical(lbook["sum_characters"])} {Tx("characters")}',
                ),
                Td(A(Tx("Differences"), href=f"/differences/{id}", role="button")),
            ),
        )

    title = Tx("Differences")
    return (
        Title(title),
        components.header(request, title),
        Main(
            Table(
                Thead(
                    Tr(
                        Th(Tx("Book")),
                        Th(os.environ["WRITETHATBOOK_REMOTE_SITE"], scope="col"),
                        Th(Tx("Here"), scope="col"),
                        Th(scope="col"),
                    ),
                ),
                Tbody(*rows),
            ),
            cls="container",
        ),
    )


@rt("/{id:str}")
def get(request, id: str):
    """Compare local book with the remote site book.
    One of them may not exist.
    """
    auth.authorize(request, *auth.book_diff)

    if not id:
        raise Error("book id may not be empty")
    if id != constants.REFS and id.startswith("_"):
        raise Error("book id may not start with an underscore '_'")

    remote_state = get_remote_state(id)

    if id == constants.REFS:
        book = get_refs()
        local_state = book.state
        title = f"{Tx('Differences in')} '{Tx('References')}'"
        rurl = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/refs"
        lurl = f"/refs"
    else:
        try:
            book = get_book(id)
            local_state = book.state
        except Error:
            local_state = {}
        title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
        rurl = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/book/{id}"
        lurl = f"/book/{id}"

    rows, rflag, lflag = items_diffs(
        remote_state.get("items", []), rurl, local_state.get("items", []), lurl
    )

    # The book 'index.md' files may differ, if they exist.
    if remote_state and local_state:
        row, rf, lf = item_diff(
            remote_state,
            rurl,
            local_state,
            lurl,
        )
        if row:
            rows.insert(0, row)
            rflag += rf
            lflag += lf

    if not rows:
        if not remote_state:
            segments = (
                H4(f'{Tx("Not present in")} {os.environ["WRITETHATBOOK_REMOTE_SITE"]}'),
                Form(
                    Button(f'{Tx("Update")} {os.environ["WRITETHATBOOK_REMOTE_SITE"]}'),
                    action=f"/diff/push/{id}",
                    method="post",
                ),
            )
        elif not local_state:
            segments = (
                H4(Tx("Not present here")),
                Form(
                    Button(Tx("Update here")),
                    action=f"/diff/pull/{id}",
                    method="post",
                ),
            )
        else:
            segments = (
                H4(Tx("Identical")),
                Div(
                    Div(Strong(A(rurl, href=rurl))),
                    Div(Strong(A(lurl, href=lurl))),
                    cls="grid",
                ),
            )

        return (
            Title(title),
            components.header(request, title, book=book),
            Main(*segments, cls="container"),
        )

    rows.append(
        Tr(
            Td(),
            Td(
                Form(
                    Button(
                        f'{Tx("Update")} {os.environ["WRITETHATBOOK_REMOTE_SITE"]}',
                        cls=None if rflag else "outline",
                    ),
                    action=f"/diff/push/{id}",
                    method="post",
                )
            ),
            Td(
                Form(
                    Button(Tx("Update here"), cls=None if lflag else "outline"),
                    action=f"/diff/pull/{id}",
                    method="post",
                ),
                colspan=3,
            ),
        )
    )

    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Table(
                Thead(
                    Tr(
                        Th(Tx("Title"), scope="col"),
                        Th(A(rurl, href=rurl), scope="col"),
                        Th(Tx("Here"), scope="col"),
                        Th(Tx("Age"), scope="col"),
                        Th(Tx("Size"), scope="col"),
                    ),
                ),
                Tbody(*rows),
            ),
            cls="container",
        ),
    )


def items_diffs(ritems, rurl, litems, lurl):
    """Return list of rows and flags specifying differences between
    remote and local items.
    """
    result = []
    rflag = 0
    lflag = 0
    for ritem in ritems:
        riurl = f'{rurl}/{ritem["name"]}'
        for pos, litem in enumerate(list(litems)):
            if litem["title"] != ritem["title"]:
                continue
            liurl = f'{lurl}/{litem["name"]}'
            row, rf, lf = item_diff(ritem, riurl, litem, liurl)
            rflag += rf
            lflag += lf
            if row:
                result.append(row)
            litems.pop(pos)
            try:
                rows, rf, lf = items_diffs(ritem["items"], riurl, litem["items"], liurl)
                rflag += rf
                lflag += lf
                result.extend(rows)
            except KeyError as message:
                pass
            break
        else:
            row, rf, lf = item_diff(ritem, riurl, None, None)
            rflag += rf
            lflag += lf
            result.append(row)
    for litem in litems:
        row, rf, lf = item_diff(None, None, litem, f'{lurl}/{litem["name"]}')
        rflag += rf
        lflag += lf
        result.append(row)
    return result, rflag, lflag


def item_diff(ritem, riurl, litem, liurl):
    "Return row and update flags specifying differences between the items."
    if ritem is None:
        return (
            Tr(
                Td(Strong(litem["title"])),
                Td("-"),
                Td("-"),
                Td("-"),
                Td(A(liurl, href=liurl)),
            ),
            1,
            0,
        )
    elif litem is None:
        return (
            Tr(
                Td(Strong(ritem["title"])),
                Td(A(riurl, href=riurl)),
                Td("-"),
                Td("-"),
                Td("-"),
            ),
            0,
            1,
        )
    if litem["digest"] == ritem["digest"]:
        return None, 0, 0
    if litem["modified"] < ritem["modified"]:
        age = "Older"
        rflag = 0
        lflag = 1
    elif litem["modified"] > ritem["modified"]:
        age = "Newer"
        rflag = 1
        lflag = 0
    else:
        age = "Same"
        rflag = 0
        lflag = 0
    if litem["n_characters"] < ritem["n_characters"]:
        size = "Smaller"
    elif litem["n_characters"] > ritem["n_characters"]:
        size = "Larger"
    else:
        size = "Same"
    return (
        Tr(
            Td(Strong(ritem["title"])),
            Td(A(riurl, href=riurl)),
            Td(A(liurl, href=liurl)),
            Td(Tx(age)),
            Td(Tx(size)),
        ),
        rflag,
        lflag,
    )


@rt("/pull/{id:str}")
def post(request, id: str):
    "Update book at this site by downloading it from the remote site."
    auth.authorize(request, *auth.book_diff)

    if not id:
        raise Error("no book id provided")

    if id == constants.REFS:
        url = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + "/refs/download"
    else:
        url = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/download/{id}"
    dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
    headers = dict(apikey=os.environ["WRITETHATBOOK_REMOTE_APIKEY"])

    response = requests.get(url, headers=headers)

    if response.status_code != HTTP.OK:
        raise Error(f"remote error: {response.content}")
    if response.headers["Content-Type"] != constants.GZIP_CONTENT_TYPE:
        raise Error("invalid file type from remote")
    content = response.content
    if not content:
        raise Error("empty TGZ file from remote")

    # Temporarily save old contents.
    if dirpath.exists():
        saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
        dirpath.replace(saved_dirpath)
    else:
        saved_dirpath = None
    try:
        unpack_tgz_content(dirpath, content, is_refs=id == constants.REFS)
    except ValueError as message:
        # If failure, reinstate saved contents.
        if saved_dirpath:
            saved_dirpath.replace(dirpath)
        raise Error(f"error reading TGZ file from remote: {message}")
    else:
        # Remove saved contents after new was successful unpacked.
        if saved_dirpath:
            shutil.rmtree(saved_dirpath)

    if id == constants.REFS:
        get_refs(reread=True)
        return components.redirect("/refs")
    else:
        get_book(id, reread=True)
        return components.redirect(f"/book/{id}")


@rt("/push/{id:str}")
def post(request, id: str):
    "Update book at the remote site by uploading it from this site."
    auth.authorize(request, *auth.book_diff)

    if not id:
        raise Error("book id may not be empty")
    if id == constants.REFS:
        book = get_refs()
    else:
        if id.startswith("_"):
            raise Error("book id may not start with an underscore '_'")
        book = get_book(id)

    url = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + f"/diff/receive/{id}"
    content = book.get_tgz_content()
    headers = dict(apikey=os.environ["WRITETHATBOOK_REMOTE_APIKEY"])
    response = requests.post(
        url,
        headers=headers,
        files=dict(tgzfile=("tgzfile", content, constants.GZIP_CONTENT_TYPE)),
    )
    if response.status_code != HTTP.OK:
        raise Error(f"remote did not accept push: {response.content}")

    return components.redirect(f"/diff/{id}")


@rt("/receive/{id:str}")
async def post(request, id: str, tgzfile: UploadFile = None):
    "Update book at local site by another site uploading it."
    auth.authorize(request, *auth.receive_diff)

    if not id:
        raise Error("book id may not be empty")
    if id != constants.REFS and id.startswith("_"):
        raise Error("book id may not start with an underscore '_'")

    content = await tgzfile.read()
    if not content:
        raise Error("no content in TGZ file")

    dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
    if dirpath.exists():
        # Temporarily save current contents.
        saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
        dirpath.rename(saved_dirpath)
    else:
        saved_dirpath = None
    try:
        unpack_tgz_content(dirpath, content, is_refs=id == constants.REFS)
        if saved_dirpath:
            shutil.rmtree(saved_dirpath)
    except ValueError as message:
        if saved_dirpath:
            saved_dirpath.rename(dirpath)
        raise Error(f"error reading TGZ file: {message}")

    if id == constants.REFS:
        get_refs(reread=True)
    else:
        get_book(id, reread=True)
    return "success"


def get_remote_state(id=None):
    "Get the remote site state, optionally for the given book id."
    if "WRITETHATBOOK_REMOTE_SITE" not in os.environ:
        raise Error("WRITETHATBOOK_REMOTE_SITE undefined", HTTP.INTERNAL_SERVER_ERROR)
    if "WRITETHATBOOK_REMOTE_APIKEY" not in os.environ:
        raise Error("WRITETHATBOOK_REMOTE_APIKEY undefined", HTTP.INTERNAL_SERVER_ERROR)

    url = os.environ["WRITETHATBOOK_REMOTE_SITE"].rstrip("/") + "/state"
    if id:
        url += "/" + id
    headers = dict(apikey=os.environ["WRITETHATBOOK_REMOTE_APIKEY"])
    response = requests.get(url, headers=headers)

    # No such book.
    if response.status_code == 404 or not response.content:
        return {}

    if response.status_code != 200:
        raise Error(
            f"remote {url} response error: {response.status_code}",
            HTTP.INTERNAL_SERVER_ERROR,
        )

    return response.json()
