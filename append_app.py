"Append text to the book, section or text."

from fasthtml.common import *

import auth
from books import Book
import components
import utils
from utils import Tx


app, rt = utils.get_fast_app()


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Append to the content of the item (book, text or section)."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    if path:
        item = book[path]
    else:
        item = book

    title = f"{Tx('Append')} {item.type} '{item.title}'"
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                Textarea(name="content", rows="20", autofocus=True),
                components.save_button("Append"),
                action=f"/append/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),  # This works for book.
            cls="container",
        ),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str, content: str):
    "Actually append to the content of the item (book, text or section)."
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

    return utils.redirect(f"/book/{book}/{path}")  # This works for book.
