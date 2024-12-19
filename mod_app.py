"Modify book contents in various ways."

from icecream import ic

from fasthtml.common import *

import auth
from books import Book
import components
import utils
from utils import Tx


app, rt = utils.get_fast_app()


@rt("/forward/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item forward in its sibling list."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].forward()
    return utils.redirect(f"/book/{book}")


@rt("/backward/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item backward in its sibling list."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].backward()
    return utils.redirect(f"/book/{book}")


@rt("/outof/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item out of its section."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].outof()
    return utils.redirect(f"/book/{book}")


@rt("/into/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item into the nearest preceding section."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].into()
    return utils.redirect(f"/book/{book}")


@rt("/append/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Append to the content of an item."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    if path:
        item = book[path]
    else:
        item = book

    title = f'{Tx("Append")} {item.title}'
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                Textarea(name="content", rows="20", autofocus=True),
                Button(Tx("Append")),
                action=f"/mod/append/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),  # This works for book.
            cls="container",
        ),
    )


@rt("/append/{book:Book}/{path:path}")
def post(request, book:Book, path: str, content: str):
    "Actually append to the content of an item."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    if path:
        item = book[path]
    else:
        item = book

    # Slot in appended content before footnotes, if any.
    lines = item.content.split("\n")
    for pos, line in enumerate(lines):
        if line.startswith("[^"):
            lines.insert(pos - 1, content + "\n")
            break
    else:
        lines.append(content)
    item.write(content="\n".join(lines))

    # Write out and reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return utils.redirect(f"/mod/append/{book}/{path}")


# @rt("/to_section/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Convert to section containing a text with this text."
#     book = books.get_book(id)
#     text = book[path]
#     assert text.is_text

#     title = f"{Tx('Convert to section')}: '{text.fulltitle}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=text.status),
#         Main(
#             Form(
#                 Button(Tx("Convert")), action=f"/to_section/{id}/{path}", method="post"
#             ),
#             components.cancel_button(f"/book/{id}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/to_section/{id:str}/{path:path}")
# def post(id: str, path: str):
#     "Actually convert to section containing a text with this text."
#     book = books.get_book(id)
#     text = book[path]
#     assert text.is_text
#     section = text.to_section()

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/book/{id}/{section.path}", status_code=HTTP.SEE_OTHER)


# @rt("/text/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Create a new text in the section."
#     book = books.get_book(id)
#     if path:
#         parent = book[path]
#         assert parent.is_section
#         title = f"{Tx('Create text in')} '{parent.fulltitle}'"
#     else:
#         title = f"{Tx('Create text in')} {Tx('book')}"

#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Form(
#                 Fieldset(
#                     Label(Tx("Title")),
#                     Input(name="title", required=True, autofocus=True),
#                 ),
#                 Button(Tx("Create")),
#                 action=f"/text/{id}/{path}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{id}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/text/{id:str}/{path:path}")
# def post(id: str, path: str, title: str = None):
#     "Actually create a new text in the section."
#     book = books.get_book(id)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_text(title, parent=parent)

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{id}/{new.path}", status_code=HTTP.SEE_OTHER)


# @rt("/section/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Create a new section in the section."
#     book = books.get_book(id)
#     if path:
#         parent = book[path]
#         assert parent.is_section
#         title = f"{Tx('Create section in')} '{parent.fulltitle}'"
#     else:
#         title = f"{Tx('Create section in')} {Tx('book')}"

#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Form(
#                 Fieldset(
#                     Label(Tx("Title")),
#                     Input(name="title", required=True, autofocus=True),
#                 ),
#                 Button(Tx("Create")),
#                 action=f"/section/{id}/{path}",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/section/{id:str}/{path:path}")
# def post(id: str, path: str, title: str = None):
#     "Actually create a new section in the section."
#     book = books.get_book(id)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_section(title, parent=parent)

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{id}/{new.path}", status_code=HTTP.SEE_OTHER)


@rt("/copy/{book:Book}")
def get(request, book: Book):
    "Make a copy of the book."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    new = book.copy(owner=auth.logged_in(request).id)
    return utils.redirect(f"/book/{new}")


@rt("/copy/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Make a copy of the item (text or section)."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    path = book[path].copy()
    return utils.redirect(f"/book/{book}/{path}")


@rt("/delete/{book:Book}")
def get(request, book: Book):
    "Confirm deleting book."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    if book.items or book.content:
        segments = [P(Strong(Tx("Note: all contents will be lost!")))]
    else:
        segments = []

    title = f"{Tx('Delete book')} '{book.title}'?"
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
        Main(
            H3(Tx("Delete"), "?"),
            *segments,
            Form(Button(Tx("Confirm")),
                 action=f"/mod/delete/{book}",
                 method="post"),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
    )


@rt("/delete/{book:Book}")
def post(request, book: Book):
    "Actually delete the book, even if it contains items."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book.delete(force=True)
    return utils.redirect("/")


@rt("/delete/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Confirm delete of the text or section; section must be empty."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    item = book[path]
    if len(item.items) != 0 or item.content:
        segments = [P(Strong(Tx("Note: all contents will be lost!")))]
    else:
        segments = []

    title = f"{Tx('Delete')} {Tx(item.type)} '{item.fulltitle}'?"
    return (
        Title(title),
        components.header(request, title, book=book, status=item.status),
        Main(
            H3(Tx("Delete"), "?"),
            *segments,
            Form(Button(Tx("Confirm")),
                 action=f"/mod/delete/{book}/{path}",
                 method="post"),
            components.cancel_button(f"/book/{book}/{path}"),
            cls="container",
        ),
    )


@rt("/delete/{book:Book}/{path:path}")
def post(request, book: Book, path: str):
    "Delete the text or section."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].delete(force=True)
    return utils.redirect(f"/book/{book}")
