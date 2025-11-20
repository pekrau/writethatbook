"Pages to modify book, section or text."

from fasthtml.common import *

import auth
from books import Book
import components
from utils import Tx


app, rt = components.get_fast_app()


@rt("/append/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Append to the content of the item (book, text or section)."
    auth.authorize(request, *auth.book_edit, book=book)

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
                Textarea(name="content", rows=16, autofocus=True),
                components.save_button("Append"),
                action=f"/mod/append/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),  # This works for book.
            cls="container",
        ),
    )


@rt("/append/{book:Book}/{path:path}")
def post(request, book: Book, path: str, content: str):
    "Actually append to the content of the item (book, text or section)."
    auth.authorize(request, *auth.book_edit, book=book)

    if path:
        item = book[path]
    else:
        item = book

    # Slot in appended content before footnotes, if any.
    old_content, footnotes = item.split_footnotes()
    item.write(content=old_content + "\n" + content + "\n\n" + footnotes)

    # Write out and reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return components.redirect(f"/book/{book}/{path}")  # This works for book.


@rt("/merge/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Join all items from this and below into a single text."
    auth.authorize(request, *auth.book_edit, book=book)

    item = book[path]
    if not item.is_section:
        raise Error(f"Item '{item}' is not a section; cannot merge.")

    title = f"{Tx('Merge')} '{item.title}'?"
    return (
        Title(title),
        components.header(request, title, book=book, item=item),
        Main(
            H3(Tx("Merge"), "?"),
            P(Strong(Tx("All subitems will be merged into one text!"))),
            Form(
                components.save_button("Confirm"),
                action=f"/mod/merge/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),
            cls="container",
        ),
    )


@rt("/merge/{book:Book}/{path:path}")
def post(request, book: Book, path: str):
    "Actually join all items from this and below into a single text."
    auth.authorize(request, *auth.book_edit, book=book)
    new = book.merge(path)
    return components.redirect(f"/book/{book}/{new}")


@rt("/split/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Split this text into section with texts below."
    auth.authorize(request, *auth.book_edit, book=book)

    item = book[path]
    if not item.is_text:
        raise Error(f"Item '{item}' is not a text; cannot split.")

    title = f"{Tx('Split')} '{item.title}'?"
    return (
        Title(title),
        components.header(request, title, book=book, item=item),
        Main(
            H3(Tx("Split"), "?"),
            P(Strong(Tx("The text will be converted into a section with subtexts!"))),
            Form(
                components.save_button("Confirm"),
                action=f"/mod/split/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),
            cls="container",
        ),
    )


@rt("/split/{book:Book}/{path:path}")
def post(request, book: Book, path: str):
    "Actually split this text into section with texts below."
    auth.authorize(request, *auth.book_edit, book=book)
    new = book.split(path)
    return components.redirect(f"/book/{book}/{new}")
