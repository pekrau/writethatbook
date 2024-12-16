"Book, section and text HTTP resources."

from icecream import ic
from json_logic import jsonLogic
from fasthtml.common import *

import auth
from books import get_book, Book


class BookConvertor(Convertor):
    regex = "[^_./][^./]*"

    def convert(self, value: str) -> Book:
        return get_book(value)

    def to_string(self, value: Book) -> str:
        return value.bid


register_url_convertor("Book", BookConvertor())


app, rt = fast_app()


@rt("/{book:Book}", name="view")
def get(request, book: Book):
    auth.authorize(
        request,
        auth.Allow({"var": "book.public"}),
        auth.deny_anonymous,
        auth.Allow({"==": [{"var": "current_user.id"}, {"var": "book.owner"}]}),
        book=book,
    )
    return repr(book)
