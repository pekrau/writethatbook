"Modify book contents in various ways."

from icecream import ic

from fasthtml.common import *

import auth
from books import Book
import components
import utils
from utils import Tx


app, rt = utils.get_fast_app()


# XXX
@rt("/to_section/{id:str}/{path:path}")
def get(id: str, path: str):
    "Convert to section containing a text with this text."
    book = books.get_book(id)
    text = book[path]
    assert text.is_text

    title = f"{Tx('Convert to section')}: '{text.fulltitle}'"
    return (
        Title(title),
        components.header(request, title, book=book, status=text.status),
        Main(
            Form(
                Button(Tx("Convert")), action=f"/to_section/{id}/{path}", method="post"
            ),
            components.cancel_button(f"/book/{id}/{path}"),
            cls="container",
        ),
    )


@rt("/to_section/{id:str}/{path:path}")
def post(id: str, path: str):
    "Actually convert to section containing a text with this text."
    book = books.get_book(id)
    text = book[path]
    assert text.is_text
    section = text.to_section()

    # Reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return utils.redirect(f"/book/{id}/{section.path}")


@rt("/text/{id:str}/{path:path}")
def get(id: str, path: str):
    "Create a new text in the section."
    book = books.get_book(id)
    if path:
        parent = book[path]
        assert parent.is_section
        title = f"{Tx('Create text in')} '{parent.fulltitle}'"
    else:
        title = f"{Tx('Create text in')} {Tx('book')}"

    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                Fieldset(
                    Label(Tx("Title")),
                    Input(name="title", required=True, autofocus=True),
                ),
                Button(Tx("Create")),
                action=f"/text/{id}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{id}/{path}"),
            cls="container",
        ),
    )


@rt("/text/{id:str}/{path:path}")
def post(id: str, path: str, title: str = None):
    "Actually create a new text in the section."
    book = books.get_book(id)
    if path == "":
        parent = None
    else:
        parent = book[path]
        assert parent.is_section
    new = book.create_text(title, parent=parent)

    # Reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return utils.redirect(f"/edit/{id}/{new.path}")


@rt("/section/{id:str}/{path:path}")
def get(id: str, path: str):
    "Create a new section in the section."
    book = books.get_book(id)
    if path:
        parent = book[path]
        assert parent.is_section
        title = f"{Tx('Create section in')} '{parent.fulltitle}'"
    else:
        title = f"{Tx('Create section in')} {Tx('book')}"

    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                Fieldset(
                    Label(Tx("Title")),
                    Input(name="title", required=True, autofocus=True),
                ),
                Button(Tx("Create")),
                action=f"/section/{id}/{path}",
                method="post",
            ),
            cls="container",
        ),
    )


@rt("/section/{id:str}/{path:path}")
def post(id: str, path: str, title: str = None):
    "Actually create a new section in the section."
    book = books.get_book(id)
    if path == "":
        parent = None
    else:
        parent = book[path]
        assert parent.is_section
    new = book.create_section(title, parent=parent)

    # Reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return utils.redirect(f"/edit/{id}/{new.path}")
