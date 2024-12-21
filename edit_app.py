"Book, section and text edit resources."

from fasthtml.common import *

import auth
import books
from books import Book
import components
import constants
from errors import *
import users
import utils
from utils import Tx


app, rt = utils.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book):
    "Edit the book data."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    fields = [
        Fieldset(
            Legend(Tx("Title")),
            Input(
                name="title",
                value=book.frontmatter["title"],
                required=True,
                autofocus=True,
            ),
        ),
        Fieldset(
            Legend(Tx("Subtitle")),
            Input(name="subtitle", value=book.frontmatter.get("subtitle", "")),
        ),
        Fieldset(
            Legend(Tx("Authors")),
            Textarea(
                "\n".join(book.frontmatter.get("authors", [])),
                name="authors",
                rows="10",
            ),
        ),
    ]
    if len(book.items) == 0:
        fields.append(
            Fieldset(
                Legend(Tx("Status")),
                components.get_status_field(book),
            )
        )
    language_options = []
    for language in constants.LANGUAGE_CODES:
        if book.frontmatter.get("language") == language:
            language_options.append(Option(language, selected=True))
        else:
            language_options.append(Option(language))
    fields.append(
        Fieldset(Legend(Tx("Language")), Select(*language_options, name="language"))
    )
    fields.append(
        Fieldset(
            Legend(Tx("Text")),
            Textarea(
                NotStr(book.content),
                name="content",
                rows="10",
            ),
        )
    )
    menu = []

    title = f"{Tx('Edit')} {Tx('book')} '{book.title}'"
    return (
        Title(title),
        components.header(request, title, book=book, menu=menu, status=book.status),
        Main(
            Form(
                *fields, components.save_button(), action=f"/edit/{book}", method="post"
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/{book:Book}")
def post(request, book: Book, form: dict):
    "Actually edit the book data."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    try:
        title = form["title"].strip()
        if not title:
            raise KeyError
        book.frontmatter["title"] = title
    except KeyError:
        raise Error("no title given for book")
    book.frontmatter["authors"] = [
        a.strip() for a in form.get("authors", "").split("\n")
    ]
    for key in ["subtitle", "status", "language"]:
        value = form.get(key, "").strip()
        if value:
            book.frontmatter[key] = value
        else:
            book.frontmatter.pop(key, None)

    # Reread the book, ensuring everything is up to date.
    book.write(content=form.get("content"), force=True)
    book.read()

    return utils.redirect(f"/book/{book}")


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Edit the item (section or text)."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    item = book[path]
    title_field = Fieldset(
        Label(Tx("Title")),
        Input(name="title", value=item.title, required=True, autofocus=True),
    )
    if item.is_text:
        item.read()
        fields = [
            Div(
                title_field,
                Fieldset(
                    Legend(Tx("Status")),
                    components.get_status_field(item),
                ),
                cls="grid",
            )
        ]
    elif item.is_section:
        fields = [title_field]
    fields.append(
        Fieldset(
            Legend(Tx("Text")),
            Textarea(NotStr(item.content), name="content", rows="20"),
        )
    )

    title = f"{Tx('Edit')} {Tx(item.type)} '{item.title}'"
    return (
        Title(title),
        components.header(request, title, book=book, status=item.status),
        Main(
            Form(
                *fields,
                components.save_button(),
                action=f"/edit/{book}/{path}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}/{path}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str, form: dict):
    "Actually edit the item (section or text)."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    item = book[path]
    item.title = form["title"]
    item.name = form["title"]  # Changes name of directory/file.
    if item.is_text:
        if form.get("status"):
            item.status = form["status"]
    item.write(content=form["content"])

    # Reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    # Must use new path, since name may have been changed.
    return utils.redirect(f"/book/{book}/{item.path}")
