"Move item (text or section) within the book."

import auth
from books import Book
import utils


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
