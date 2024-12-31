"Book, section and text edit pages."

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


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book, first: int = None, last: int = None):
    "Edit the book data, possibly one single paragraph of the content."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    # Digest of content only, not frontmatter!
    fields = [Input(type="hidden", name="digest", value=utils.get_digest(book.content))]

    if first is None:  # Full edit.
        fields.append(
            Div(
                Div(
                    Fieldset(
                        Legend(Tx("Title")),
                        Input(
                            name="title",
                            value=book.title,
                            required=True,
                            autofocus=True,
                        ),
                    ),
                ),
                Div(
                    Fieldset(
                        Legend(Tx("Subtitle")),
                        Input(name="subtitle", value=book.subtitle or ""),
                    ),
                ),
                cls="grid",
            )
        )
        language_options = []
        for language in constants.LANGUAGE_CODES:
            if book.language == language:
                language_options.append(Option(language, selected=True))
            else:
                language_options.append(Option(language))
        right = [
            Fieldset(
                Legend(Tx("Language")), Select(*language_options, name="language")
            ),
            Fieldset(
                Legend(Tx("Public")),
                Label(
                    Input(
                        type="checkbox",
                        role="switch",
                        name="public",
                        checked=book.public,
                    ),
                    Tx("Readable by anyone."),
                ),
            ),
        ]
        if book.type == constants.ARTICLE:
            right.append(
                Fieldset(
                    Legend(Tx("Status")),
                    components.get_status_field(book),
                )
            )
        fields.append(
            Div(
                Div(
                    Fieldset(
                        Legend(Tx("Authors")),
                        Textarea(
                            "\n".join(book.authors or []),
                            id="authors",
                            name="authors",
                            rows=4,
                        ),
                    ),
                ),
                Div(*right),
                cls="grid",
            ),
        )
        fields.append(
            Fieldset(
                Legend(Tx("Text")),
                Textarea(
                    NotStr(book.content.replace("LASTEDIT", "")),
                    id="text",
                    name="content",
                    rows=16,
                ),
            )
        )

    else:  # Edit only the given content fragment (paragraph).
        content = book.content[first:last].replace("LASTEDIT", "")
        fields.extend(
            [
                Input(type="hidden", name="first", value=str(first)),
                Input(type="hidden", name="last", value=str(last)),
                Fieldset(
                    Legend(Tx("Paragraph text")),
                    Textarea(
                        NotStr(content),
                        id="content",
                        name="content",
                        rows=16,
                        autofocus=True,
                    ),
                ),
            ]
        )

    title = f"{Tx('Edit')} {Tx('book')} '{book.title}'"
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
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

    if form.get("digest") != utils.get_digest(book.content):
        raise Error("text content changed while editing")

    first = form.get("first")
    if first is None:  # Full edit.
        try:
            title = form["title"].strip()
            if not title:
                raise KeyError
            book.title = title
        except KeyError:
            raise Error("no title given for book")
        book.subtitle = form.get("subtitle") or ""
        book.authors = [a.strip() for a in (form.get("authors") or "").split("\n")]
        book.public = bool(form.get("public", ""))
        if book.type == constants.ARTICLE:
            book.status = form.get("status")
        book.language = form.get("language", "")
        content = form["content"]
        href = f"/book/{book}"

    else:  # Edit only the given content fragment (paragraph).
        try:
            first = int(first)
            last = int(form["last"])
        except (KeyError, ValueError, TypeError):
            raise Error("bad first or last value")
        # Remove any old LASTEDIT markers.
        content = book.content
        before = content[:first].replace("LASTEDIT", "")
        after = content[last:].replace("LASTEDIT", "")
        content = before + "LASTEDIT" + (form.get("content") or "") + after
        href = f"/book/{book}#lastedit"

    # Save book content. Reread the book, ensuring everything is up to date.
    book.write(content=content, force=True)
    book.read()

    return components.redirect(href)


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str, first: int = None, last: int = None):
    "Edit the item (section or text), possibly one single paragraph of the content.."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    item = book[path]
    fields = [Input(type="hidden", name="digest", value=utils.get_digest(item.content))]

    if first is None:  # Full edit.
        title_field = Fieldset(
            Label(Tx("Title")),
            Input(name="title", value=item.title, required=True))
        subtitle_field = Fieldset(
            Label(Tx("Subtitle")),
            Input(name="subtitle", value=item.subtitle or ""))
        if item.is_text:
            item.read()
            fields.append(
                Div(
                    title_field,
                    subtitle_field,
                    Fieldset(
                        Legend(Tx("Status")),
                        components.get_status_field(item),
                    ),
                    cls="grid",
                )
            )
        elif item.is_section:
            fields.append(Div(title_field, subtitle_field, cls="grid"))

        fields.append(
            Fieldset(
                Legend(Tx("Text")),
                Textarea(
                    NotStr(item.content.replace("LASTEDIT", "")),
                    id="content",
                    name="content",
                    rows=16,
                    autofocus=True,
                ),
            )
        )

    else:  # Edit only the given content fragment (paragraph).
        content = item.content[first:last].replace("LASTEDIT", "")
        fields.extend(
            [
                Input(type="hidden", name="first", value=str(first)),
                Input(type="hidden", name="last", value=str(last)),
                Fieldset(
                    Legend(Tx("Paragraph text")),
                    Textarea(
                        NotStr(content),
                        id="content",
                        name="content",
                        rows=16,
                        autofocus=True,
                    ),
                ),
            ]
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
    if form.get("digest") != utils.get_digest(item.content):
        raise Error("text content changed while editing")

    first = form.get("first")
    if first is None:  # Full edit.
        item.name = form["title"]  # Changes name of directory/file.
        item.title = form["title"]
        item.subtitle = form.get("subtitle") or ""
        if item.is_text:
            if form.get("status"):
                item.status = form["status"]
        content = form["content"]
        # Compute new path; item name may have changed.
        href = f"/book/{book}/{item.path}"

    else:  # Edit only the given content fragment (paragraph).
        try:
            first = int(first)
            last = int(form["last"])
        except (KeyError, ValueError, TypeError):
            raise Error("bad first or last value")
        # Remove any old LASTEDIT markers.
        content = item.content
        before = content[:first].replace("LASTEDIT", "")
        after = content[last:].replace("LASTEDIT", "")
        content = before + "LASTEDIT" + (form.get("content") or "") + after
        href = f"/book/{book}/{path}#lastedit"

    # Save item. Reread the book, ensuring everything is up to date.
    item.write(content=content, force=True)
    book.write()
    book.read()

    # Must use new path, since name may have been changed.
    return components.redirect(href)
