"Return JSON file for the current state of the site or a book."

import auth
from books import Book, get_books, get_refs
import components
import constants
import utils


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Return JSON for the overall state of this site."
    auth.allow_admin(request)

    books = {}
    for book in get_books(request) + [get_refs()]:
        books[book.id] = dict(
            title=book.title,
            modified=utils.timestr(
                filepath=book.absfilepath, localtime=False, display=False
            ),
            n_items=len(book.all_items),
            sum_characters=book.frontmatter["sum_characters"],
            digest=book.frontmatter["digest"],
        )

    return dict(
        software=constants.SOFTWARE,
        version=constants.__version__,
        now=utils.timestr(localtime=False, display=False),
        books=books,
    )


@rt("/{book:Book}")
def get(request, book: Book):
    "Return JSON for the state of the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    result = dict(
        software=constants.SOFTWARE,
        version=constants.__version__,
        now=utils.timestr(localtime=False, display=False),
    )
    result.update(book.state)

    return result
