"Copy an item (book, text or section)."

import auth
from books import Book
import components


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book):
    "Make a copy of the book."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    new = book.copy(owner=auth.logged_in(request).id)
    return components.redirect(f"/book/{new}")


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Make a copy of the item (text or section)."
    auth.authorize(request, *auth.book_edit_rules, book=book)
    path = book[path].copy()
    return components.redirect(f"/book/{book}/{path}")
