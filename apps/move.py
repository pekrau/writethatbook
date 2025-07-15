"Move item (text or section) within the book."

import auth
from books import Book
import components


app, rt = components.get_fast_app()


@rt("/forward/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item forward in its sibling list."
    auth.authorize(request, *auth.book_edit, book=book)
    book[path].forward()
    return components.redirect(request.headers["referer"])


@rt("/backward/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item backward in its sibling list."
    auth.authorize(request, *auth.book_edit, book=book)
    book[path].backward()
    return components.redirect(request.headers["referer"])


@rt("/outof/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item out of its section."
    auth.authorize(request, *auth.book_edit, book=book)
    book[path].outof()
    return components.redirect(request.headers["referer"])


@rt("/into/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Move item into the nearest preceding section."
    auth.authorize(request, *auth.book_edit, book=book)
    book[path].into()
    return components.redirect(request.headers["referer"])
