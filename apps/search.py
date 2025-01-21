"Search text in book or section."

from fasthtml.common import *

import auth
import books
from books import Book
import components
import utils
from utils import Tx


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def post(request, book: Book, form: dict):
    "Actually search the book for a given term."
    auth.authorize(request, *auth.book_view_rules, book=book)

    term = form.get("term")
    if term:
        # Ignore case only when term is in all lower-case.
        ignorecase = term == term.lower()
        items = [
            Li(A(i.fulltitle, href=f"/book/{book}/{i.path}"))
            for i in sorted(
                book.search(utils.wildcard_to_regexp(term), ignorecase=ignorecase),
                key=lambda i: i.ordinal,
            )
        ]
        if items:
            result = P(Ul(*items))
        else:
            result = P(f'{Tx("No result")}.')
    else:
        result = P()

    title = f"{Tx('Search in')} '{book.title}'"
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status, search=False),
        Main(
            components.search_form(f"/search/{book}", term=term, autofocus=True),
            result,
            cls="container",
        ),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str, form: dict):
    "Actually search the item (text or section) for a given term."
    auth.authorize(request, *auth.book_view_rules, book=book)

    item = book[path]
    term = form.get("term")
    if term:
        # Ignore case only when term is in all lower-case.
        ignorecase = term == term.lower()
        items = [
            Li(A(i.fulltitle, href=i.path))
            for i in sorted(
                item.search(utils.wildcard_to_regexp(term), ignorecase=ignorecase),
                key=lambda i: i.ordinal,
            )
        ]
        if items:
            result = P(Ul(*items))
        else:
            result = P(f'{Tx("No result")}.')
    else:
        result = P()

    title = f"{Tx('Search in')} '{book.title}'; '{item.fulltitle}'"
    return (
        Title(title),
        components.header(request, title, book=book, status=item.status, search=False),
        Main(
            components.search_form(f"/search/{book}/{path}", term=term, autofocus=True),
            result,
            cls="container",
        ),
    )
