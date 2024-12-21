"Pages for deleting an item (book, text or section)."

from fasthtml.common import *

import auth
from books import Book
import components
from utils import Tx


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book):
    "Confirm deleting the book."
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
            Form(
                components.save_button("Confirm"),
                action=f"/delete/{book}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
    )


@rt("/{book:Book}")
def post(request, book: Book):
    "Actually delete the book, even if it contains items."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book.delete(force=True)
    return components.redirect("/")


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Confirm delete of the text or section."
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
            Form(
                components.save_button("Confirm"),
                action=f"/delete/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),
            cls="container",
        ),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str):
    "Delete the text or section."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    book[path].delete(force=True)
    return components.redirect(f"/book/{book}")
