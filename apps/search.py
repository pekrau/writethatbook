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
def get(request, book: Book):
    "Form for searching the book for a given term."
    auth.authorize(request, *auth.book_view_rules, book=book)

    title = f"{Tx('Search in')} {Tx('book')}"
    return (
        Title(title),
        components.header(request, title, book=book, search=False),
        Main(
            components.search_form(book),
            cls="container",
        ),
    )


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

    title = f"{Tx('Search in')} {Tx('book')}"
    return (
        Title(title),
        components.header(request, title, book=book, search=False),
        Main(
            components.search_form(book, term=term),
            result,
            cls="container",
        ),
    )
