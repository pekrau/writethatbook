"Book, section and text view resources."

from icecream import ic

from http import HTTPStatus as HTTP
import os

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
import docx_creator
import pdf_creator


class BookConvertor(Convertor):
    regex = "[^_./][^./]*"

    def convert(self, value: str) -> Book:
        return books.get_book(value)

    def to_string(self, value: Book) -> str:
        return value.id


register_url_convertor("Book", BookConvertor())


app, rt = utils.get_fast_app()


@rt("/")
def get(request):
    "Create and/or upload book using a gzipped tar file."
    auth.authorize(request, *auth.book_create_rules)
    title = Tx("Create or upload book")
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("Title")),
                    Input(name="title", required=True, autofocus=True),
                ),
                Fieldset(
                    Legend(Tx(f'{Tx("Upload")} {Tx("TGZ file")} ({Tx("optional")}).')),
                    Input(type="file", name="tgzfile"),
                ),
                Button(Tx("Create")),
                action="/book",
                method="post",
            ),
            cls="container",
        ),
    )


@rt("/")
async def post(request, title: str, tgzfile: UploadFile):
    "Actually create and/or upload book using a gzipped tar file."
    auth.authorize(request, *auth.book_create_rules)
    if not title:
        raise Error("book title may not be empty")
    if title.startswith("_"):
        raise Error("book title may not start with an underscore '_'")
    id = utils.nameify(title)
    if not id:
        raise Error("book id may not be empty")
    dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
    if dirpath.exists():
        raise Error(f"book '{id}' already exists", HTTP.CONFLICT)

    content = await tgzfile.read()
    if content:
        try:
            books.unpack_tgzfile(dirpath, content)
        except ValueError as message:
            raise Error(f"error reading TGZ file: {message}")
    # Just create the directory; no content.
    else:
        dirpath.mkdir()

    # Re-read all books, ensuring everything is up to date.
    books.read_books()
    # Set the title and owner of the new book.
    book = books.get_book(id)
    book.frontmatter["title"] = title or book.title
    book.frontmatter["owner"] = str(auth.logged_in())
    book.write()

    return utils.redirect(f"/book/{book}")


@rt("/{book:Book}")
def get(request, book: Book):
    "View book; contents list of sections and texts."
    auth.authorize(request, *auth.book_view_rules, book=book)

    # Update the 'index.md' file, if any previous changes.
    book.write()

    if auth.authorized(request, *auth.book_edit_rules, book=book):
        actions = [
            ("Edit", f"/edit/{book}"),
            ("Append", f"/mod/append/{book}/"),
            ("Create section", f"/mod/section/{book}"),
            ("Create text", f"/mod/text/{book}"),
            ("Copy", f"/mod/copy/{book}"),
            ("Delete", f"/mod/delete/{book}")
        ]
    else:
        actions = []
    if auth.is_admin(request) and "WRITETHATBOOK_UPDATE_SITE" in os.environ:
        actions.append(("Differences", f"/sync/diffs/{book}"))
    pages = [
        ("Index", f"/meta/index/{book}"),
        ("Recently modified", f"/meta/recent/{book}"),
        ("Status list", f"/meta/status/{book}"),
        ("Information", f"/meta/info/{book}"),
        ("State (JSON)", f"/meta/state/{book}"),
        ("Download DOCX file", f"/book/{book}.docx"),
        ("Download PDF file", f"/book/{book}.pdf"),
        ("Download TGZ file", f"/book/{book}.tgz"),
    ]

    segments = [components.search_form(f"/search/{id}")]

    if len(book.items) == 0:
        segments.append(H3(book.title))
        if book.subtitle:
            segments.append(H4(book.subtitle))
        for author in book.authors:
            segments.append(H5(author))
    else:
        segments.append(toc(book, book.items, show_arrows=True))

    return (
        Title(book.title),
        components.header(request, Tx("Contents"), book=book, status=book.status, actions=actions, pages=pages),
        Main(
            *segments,
            Div(NotStr(book.html)),
            Card(
                Div(A(Tx("Edit"), role="button", href=f"/edit/{book}")),
                Div(A(Tx("Append"), role="button", href=f"/mod/append/{book}/")),
                cls="grid",
            ),
            cls="container",
        ),
        components.footer(book),
    )


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "View book text or section contents."
    auth.authorize(request, *auth.book_view_rules, book=book)
    if not path:
        return utils.redirect(f"/book/{book}")

    item = book[path]

    if auth.authorized(request, *auth.book_edit_rules, book=book):
        actions = [
            ("Edit", f"/edit/{book}/{path}"),
            ("Append", f"/mod/append/{book}/{path}"),
        ]
        if item.is_text:
            actions.append(["Convert to section", f"/to_section/{id}/{path}"])
        elif item.is_section:
            actions.extend([
                ("Create section", f"/mod/section/{book}/{path}"),
                ("Create text", f"/mod/text/{book}/{path}"),
            ])
        actions.extend([
            ("Copy", f"/mod/copy/{book}/{path}"),
            ("Delete", f"/mod/delete/{book}/{path}")
        ])
        edit_buttons = Card(
            Div(A(Tx("Edit"), role="button", href=f"/edit/{book}/{path}")),
            Div(A(Tx("Append"), role="button", href=f"/mod/append/{book}/{path}")),
            cls="grid",
        )
    else:
        actions = []
        edit_buttons = ""
    
    pages = []
    if item.parent:
        if item.parent.level == 0:  # Book.
            url = f"/book/{book}"
        else:
            url = f"/book/{book}/{item.parent.path}"
        pages.append([f"&ShortUpArrow; {item.parent.title}", url])
    if item.prev:
        url = f"/book/{book}/{item.prev.path}"
        pages.append([f"&ShortLeftArrow; {item.prev.title}", url])
    if item.next:
        url = f"/book/{book}/{item.next.path}"
        pages.append([f"&ShortRightArrow; {item.next.title}", url])
    pages.extend([
        ("References", "/refs"),
        ("Index", f"/meta/index/{book}")
    ])

    if item.is_text:
        segments = [H3(item.heading)]
    elif item.is_section:
        segments = [
            Div(
                Div(H3(item.heading)),
                Div(components.search_form(f"/search/{id}/{path}")),
                cls="grid",
            ),
            toc(book, item.items),
        ]

    return (
        Title(item.title),
        components.header(request, item.title, book=book, status=item.status, actions=actions, pages=pages),
        Main(
            *segments,
            edit_buttons,
            Div(NotStr(item.html), style="margin-top: 1em;"),
            edit_buttons,
            cls="container",
        ),
        components.footer(item),
    )


def toc(book, items, show_arrows=False):
    "Recursive lists of sections and texts."
    parts = []
    for item in items:
        if show_arrows:
            arrows = [
                components.blank(0),
                A(
                    NotStr("&ShortUpArrow;"),
                    title=Tx("Backward"),
                    cls="plain",
                    href=f"/mod/backward/{book}/{item.path}",
                ),
                components.blank(0),
                A(
                    NotStr("&ShortDownArrow;"),
                    title=Tx("Forward"),
                    cls="plain",
                    href=f"/mod/forward/{book}/{item.path}",
                ),
            ]
            if item.parent is not book:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortLeftArrow;"),
                        title=Tx("Out of"),
                        cls="plain",
                        href=f"/mod/outof/{book}/{item.path}",
                    )
                )
            if item.prev_section:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortRightArrow;"),
                        title=Tx("Into"),
                        cls="plain",
                        href=f"/mod/into/{book}/{item.path}",
                    )
                )
        else:
            arrows = []
        parts.append(
            Li(
                A(
                    item.title,
                    style=f"color: {item.status.color};",
                    href=f"/book/{item.book}/{item.path}",
                ),
                components.blank(0.5),
                Small(
                    f"{Tx(item.type)}; ",
                    f"{Tx(repr(item.status))}; ",
                    f'{utils.thousands(item.n_words)} {Tx("words")}; ',
                    f'{utils.thousands(item.n_characters)} {Tx("characters")}',
                ),
                *arrows,
            )
        )
        if item.is_section:
            parts.append(toc(book, item.items, show_arrows=show_arrows))
    return Ol(*parts)


@rt("/{book:Book}.docx")
def get(request, book: Book):
    "Download the DOCX for the book. First get the parameters."
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("docx", {})
    title_page_metadata = settings.get("title_page_metadata", True)
    page_break_level = settings.get("page_break_level", 1)
    page_break_options = []
    for value in range(0, 7):
        if value == page_break_level:
            page_break_options.append(Option(str(value), selected=True))
        else:
            page_break_options.append(Option(str(value)))
    footnotes_location = settings.get(
        "footnotes_location", constants.FOOTNOTES_EACH_TEXT
    )
    footnotes_options = []
    for value in constants.FOOTNOTES_LOCATIONS:
        if value == footnotes_location:
            footnotes_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            footnotes_options.append(Option(Tx(value.capitalize()), value=value))
    reference_font = settings.get("reference_font", constants.NORMAL)
    reference_options = []
    for value in constants.FONT_STYLES:
        if value == reference_font:
            reference_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            reference_options.append(Option(Tx(value.capitalize())))
    indexed_font = settings.get("indexed_font", constants.NORMAL)
    indexed_options = []
    for value in constants.FONT_STYLES:
        if value == indexed_font:
            indexed_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            indexed_options.append(Option(Tx(value.capitalize()), value=value))
    fields = [
        Fieldset(
            Legend(Tx("Metadata on title page")),
            Label(
                Input(
                    type="checkbox",
                    name="title_page_metadata",
                    role="switch",
                    checked=bool(title_page_metadata),
                ),
                Tx("Display"),
            ),
        ),
        Fieldset(
            Legend(Tx("Page break level")),
            Select(*page_break_options, name="page_break_level"),
        ),
        Fieldset(
            Legend(Tx("Footnotes location")),
            Select(*footnotes_options, name="footnotes_location"),
        ),
        Fieldset(
            Legend(Tx("Reference font")),
            Select(*reference_options, name="reference_font"),
        ),
        Fieldset(
            Legend(Tx("Indexed font")), Select(*indexed_options, name="indexed_font")
        ),
    ]

    title = f'{Tx("Download")} {Tx("DOCX file")}: {book.title}'
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
        Main(
            Form(
                *fields,
                Button(f'{Tx("Download")} {Tx("DOCX file")}'),
                action=f"/book/{book}.docx",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
    )


@rt("/{book:Book}.docx")
def post(request, book: Book, form: dict):
    "Actually download the DOCX file of the entire book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("docx", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["page_break_level"] = int(form["page_break_level"])
    settings["footnotes_location"] = form["footnotes_location"]
    settings["reference_font"] = form["reference_font"]
    settings["indexed_font"] = form["indexed_font"]

    # Save settings.
    if auth.authorized(request, *auth.book_edit_rules, book=book):
        book.write()

    return Response(
        content=docx_creator.Creator(book, books.get_refs()).content(),
        media_type=constants.DOCX_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.docx"'},
    )


@rt("/{book:Book}.pdf")
def get(request, book: Book):
    "Download the PDF file for the book. First get the parameters."
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    title_page_metadata = settings.get("title_page_metadata", True)
    page_break_level = settings.get("page_break_level", 1)
    page_break_options = []
    for value in range(0, 7):
        if value == page_break_level:
            page_break_options.append(Option(str(value), selected=True))
        else:
            page_break_options.append(Option(str(value)))
    contents_pages = settings.get("contents_pages", True)
    contents_level = settings.get("contents_level", 1)
    contents_level_options = []
    for value in range(0, 7):
        if value == contents_level:
            contents_level_options.append(Option(str(value), selected=True))
        else:
            contents_level_options.append(Option(str(value)))

    footnotes_location = settings.get(
        "footnotes_location", constants.FOOTNOTES_EACH_TEXT
    )
    footnotes_options = []
    for value in constants.FOOTNOTES_LOCATIONS:
        if value == footnotes_location:
            footnotes_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            footnotes_options.append(Option(Tx(value.capitalize()), value=value))

    indexed_xref = settings.get("indexed_xref", constants.PDF_PAGE_NUMBER)
    indexed_options = []
    for value in constants.PDF_INDEXED_XREF_DISPLAY:
        if value == indexed_xref:
            indexed_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            indexed_options.append(Option(Tx(value.capitalize()), value=value))

    fields = [
        Fieldset(
            Legend(Tx("Metadata on title page")),
            Label(
                Input(
                    type="checkbox",
                    name="title_page_metadata",
                    role="switch",
                    checked=bool(title_page_metadata),
                ),
                Tx("Display"),
            ),
        ),
        Fieldset(
            Legend(Tx("Page break level")),
            Select(*page_break_options, name="page_break_level"),
        ),
        Fieldset(
            Legend(Tx("Contents pages")),
            Label(
                Input(
                    type="checkbox",
                    name="contents_pages",
                    role="switch",
                    checked=bool(contents_pages),
                ),
                Tx("Display in output"),
            ),
        ),
        Fieldset(
            Legend(Tx("Contents level")),
            Select(*contents_level_options, name="contents_level"),
        ),
        Fieldset(
            Legend(Tx("Footnotes location")),
            Select(*footnotes_options, name="footnotes_location"),
        ),
        Fieldset(
            Legend(Tx("Display of indexed term reference")),
            Select(*indexed_options, name="indexed_xref"),
        )
    ]

    title = f'{Tx("Download")} {Tx("PDF file")}'
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
        Main(
            Form(
                *fields,
                Button(f'{Tx("Download")} {Tx("PDF file")}'),
                action=f"/book/{book}.pdf",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
    )


@rt("/{book:Book}.pdf")
def post(request, book: Book, form: dict):
    "Actually download the PDF file for the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["page_break_level"] = form["page_break_level"]
    settings["contents_pages"] = form["contents_pages"]
    settings["contents_level"] = form["contents_level"]
    settings["footnotes_location"] = form["footnotes_location"]
    settings["indexed_xref"] = form["indexed_xref"]

    # Save settings.
    if auth.authorized(request, *auth.book_edit_rules, book=book):
        book.write()

    return Response(
        content=pdf_creator.Creator(book, books.get_refs()).content(),
        media_type=constants.PDF_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.pdf"'},
    )


@rt("/{book:Book}.tgz")
def get(request, book: Book):
    "Download a gzipped tar file of the book."
    auth.authorize(request, *auth.book_view_rules, book=book)

    filename = f"writethatbook_{book}_{utils.timestr(safe=True)}.tgz"

    return Response(
        content=book.get_tgzfile(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
