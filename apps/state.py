"Return JSON file for the current state of the site or a book."

import datetime

import auth
from books import Book, get_books, get_refs
import components
import constants
import utils


app, rt = components.get_fast_app()


def get_books_state(request):
    "Return JSON for the state of the readable books of this site."
    result = {}
    for book in get_books(request) + [get_refs()]:
        result[book.id] = dict(
            title=book.title,
            modified=utils.str_datetime_iso(book.modified),
            sum_characters=book.sum_characters,
            digest=book.digest,
        )
    return result


def get_general_state():
    "Return JSON for the general state of this instance."
    return dict(
        software=constants.SOFTWARE,
        version=constants.__version__,
        now=utils.str_datetime_iso(datetime.datetime.now(tz=datetime.UTC)),
    )


@rt("/")
def get(request):
    "Return JSON for the overall state of this site."
    auth.allow_admin(request)
    result = get_general_state()
    result["type"] = "site"
    result["books"] = get_books_state(request)
    return result


@rt(f"/{constants.REFS}")
def get(request):
    auth.authorize(request, *auth.book_view)
    result = get_general_state()
    result.update(get_refs().state)
    return result


@rt("/{book:Book}")
def get(request, book: Book):
    "Return JSON for the state of the book."
    auth.authorize(request, *auth.book_view, book=book)
    result = get_general_state()
    result.update(book.state)
    return result
