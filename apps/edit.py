"Book, section and text edit pages."

from fasthtml.common import *

import auth
import books
from books import Book
import components
import constants
from errors import *
from markdown import Chunked
import users
import utils
from utils import Tx


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book, nchunk: int = None):
    "Edit the book data, possibly a specific chunk of the content."
    auth.authorize(request, *auth.book_edit, book=book)

    # Digest of content only, not frontmatter!
    fields = [Input(type="hidden", name="digest", value=utils.get_digest(book.content))]

    if nchunk is None:  # Edit the full content.
        fields.append(
            Div(
                Div(
                    Fieldset(
                        Label(Tx("Title")),
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
                        Label(Tx("Subtitle")),
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
            Fieldset(Label(Tx("Language")), Select(*language_options, name="language")),
            Fieldset(
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
            Fieldset(
                Label(
                    Input(
                        type="checkbox",
                        role="switch",
                        name="chunk_numbers",
                        checked=book.chunk_numbers,
                    ),
                    Tx("Display chunk numbers."),
                ),
            ),
            Fieldset(
                Label(
                    Input(
                        type="checkbox",
                        role="switch",
                        name="toc_synopsis",
                        checked=book.toc_synopsis,
                    ),
                    Tx("Display synopsis in table of contents."),
                ),
            ),
        ]
        if book.type == constants.ARTICLE:
            right.append(
                Fieldset(
                    Label(Tx("Status")),
                    components.get_status_field(book),
                )
            )
        fields.append(
            Div(
                Div(
                    Fieldset(
                        Label(Tx("Authors")),
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
                Label(Tx("Text")),
                Textarea(
                    NotStr(book.content),
                    id="text",
                    name="content",
                    rows=16,
                ),
            )
        )
        cancel_url = f"/book/{book}"

    else:  # Edit only the given chunk of content.
        chunked = Chunked(book.content)
        content = chunked.get(nchunk)
        fields.extend(
            [
                Input(type="hidden", name="nchunk", value=nchunk),
                Fieldset(
                    Label(Tx("Chunk")),
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
        cancel_url = f"/book/{book}#{nchunk}"

    title = f"{Tx('Edit')} {Tx('book')} '{book.title}'"
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                *fields, components.save_button(), action=f"/edit/{book}", method="post"
            ),
            components.cancel_button(cancel_url),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/{book:Book}")
def post(request, book: Book, form: dict):
    "Actually edit the book data."
    auth.authorize(request, *auth.book_edit, book=book)

    if form.get("digest") != utils.get_digest(book.content):
        raise Error("text content changed while editing")

    nchunk = form.get("nchunk")
    if nchunk is None:  # Edit the full content.
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
        book.chunk_numbers = bool(form.get("chunk_numbers", ""))
        book.toc_synopsis = bool(form.get("toc_synopsis", ""))
        if book.type == constants.ARTICLE:
            book.status = form.get("status")
        book.language = form.get("language", "")
        content = form["content"]
        href = f"/book/{book}"

    else:  # Edit only the given chunk of content.
        try:
            nchunk = int(nchunk)
        except (KeyError, ValueError, TypeError):
            raise Error("bad chunk number")
        chunked = Chunked(book.content)
        chunked.replace(form.get("content") or "", nchunk)
        content = chunked.content
        href = f"/book/{book}#{nchunk}"

    # Save book content. Reread the book, ensuring everything is up to date.
    book.write(content=content, force=True)
    book.read()

    return components.redirect(href)


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str, nchunk: int = None):
    "Edit the item (section or text), possibly one single paragraph of the content."
    auth.authorize(request, *auth.book_edit, book=book)

    item = book[path]
    fields = [Input(type="hidden", name="digest", value=utils.get_digest(item.content))]

    if nchunk is None:  # Edit the full content.
        title_field = Fieldset(
            Label(Tx("Title")), Input(name="title", value=item.title, required=True)
        )
        subtitle_field = Fieldset(
            Label(Tx("Subtitle")), Input(name="subtitle", value=item.subtitle or "")
        )
        if item.is_text:
            item.read()
            fields.append(
                Div(
                    title_field,
                    subtitle_field,
                    Fieldset(
                        Label(Tx("Status")),
                        components.get_status_field(item),
                    ),
                    cls="grid",
                )
            )
        elif item.is_section:
            fields.append(Div(title_field, subtitle_field, cls="grid"))

        fields.append(
            Fieldset(
                Label(Tx("Synopsis")),
                Textarea(
                    item.synopsis or "",
                    id="synopsis",
                    name="synopsis",
                    rows=2,
                ),
            )
        )
        fields.append(
            Fieldset(
                Label(Tx("Text")),
                Textarea(
                    NotStr(item.content),
                    id="content",
                    name="content",
                    rows=16,
                    autofocus=True,
                ),
            )
        )
        cancel_url = f"/book/{book}/{path}"

    else:  # Edit only the given chunk of content.
        chunked = Chunked(item.content)
        content = chunked.get(nchunk)
        fields.extend(
            [
                Input(type="hidden", name="nchunk", value=str(nchunk)),
                Fieldset(
                    Label(Tx("Chunk")),
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
        cancel_url = f"/book/{book}/{path}#{nchunk}"

    title = f"{Tx('Edit')} {Tx(item.type)} '{item.title}'"
    return (
        Title(title),
        components.header(request, title, book=book, item=item),
        Main(
            Form(
                *fields,
                components.save_button(),
                action=f"/edit/{book}/{path}",
                method="post",
            ),
            components.cancel_button(cancel_url),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str, form: dict):
    "Actually edit the item (section or text)."
    auth.authorize(request, *auth.book_edit, book=book)

    item = book[path]
    if form.get("digest") != utils.get_digest(item.content):
        raise Error("text content changed by some other action")

    nchunk = form.get("nchunk")
    if nchunk is None:  # Edit the full content.
        item.name = form["title"]  # Changes name of directory/file.
        item.title = form["title"]
        item.subtitle = form.get("subtitle") or ""
        if item.is_text:
            if form.get("status"):
                item.status = form["status"]
        item.synopsis = form.get("synopsis") or None
        content = form["content"]
        # Compute new path; item name may have changed.
        href = f"/book/{book}/{item.path}"

    else:  # Edit only the given chunk of content.
        try:
            nchunk = int(nchunk)
        except (KeyError, ValueError, TypeError):
            raise Error("bad chunk number")
        chunked = Chunked(item.content)
        chunked.replace(form.get("content") or "", nchunk)
        content = chunked.content
        href = f"/book/{book}/{path}#{nchunk}"

    # Save item. Reread the book, ensuring everything is up to date.
    item.write(content=content, force=True)
    book.write()
    book.read()

    # Must use new path, since name may have been changed.
    return components.redirect(href)
