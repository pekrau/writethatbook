"Book, section and text HTTP view resources."

from icecream import ic

import os

from fasthtml.common import *
from json_logic import jsonLogic

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
    regex = "[^./][^./]*"

    def convert(self, value: str) -> Book:
        return books.get_book(value)

    def to_string(self, value: Book) -> str:
        return value.id


register_url_convertor("Book", BookConvertor())


# Access rule sets.
book_view_rules = [
    auth.Allow({"var": "book.public"}),
    auth.Deny({"!": {"var": "current_user"}}),
    auth.Allow({"==": [{"var": "book.owner"}, {"var": "current_user.id"}]}),
    auth.Allow({"var": "current_user.is_admin"}),
]
book_edit_rules = [
    auth.Deny({"!": {"var": "current_user"}}),
    auth.Allow({"==": [{"var": "book.owner"}, {"var": "current_user.id"}]}),
    auth.Allow({"var": "current_user.is_admin"}),
]
book_create_rules = [
    auth.Allow({"!!": {"var": "current_user"}}),
]


app, rt = fast_app(
    live="WRITETHATBOOK_DEVELOPMENT" in os.environ,
    static_path="static",
    before=users.set_current_user,
    hdrs=(Link(rel="stylesheet", href="/mods.css", type="text/css"),),
    exception_handlers={
        Error: error_handler,
        NotAllowed: not_allowed_handler,
    },
)
setup_toasts(app)


@rt("/")
def get(request):
    "Create and/or upload book using a gzipped tar file."
    auth.authorize(request, *book_create_rules)
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
    auth.authorize(request, *book_create_rules)
    if not title:
        raise Error("book title may not be empty", HTTP.BAD_REQUEST)
    if title.startswith("_"):
        raise Error("book title may not start with an underscore '_'", HTTP.BAD_REQUEST)
    id = utils.nameify(title)
    if not id:
        raise Error("book id may not be empty", HTTP.BAD_REQUEST)
    dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
    if dirpath.exists():
        raise Error(f"book '{id}' already exists", HTTP.CONFLICT)

    content = await tgzfile.read()
    if content:
        try:
            books.unpack_tgzfile(dirpath, content)
        except ValueError as message:
            raise Error(f"error reading TGZ file: {message}", HTTP.BAD_REQUEST)
    # Just create the directory; no content.
    else:
        dirpath.mkdir()

    # Re-read all books, ensuring everything is up to date.
    books.read_books()
    # Set the title and owner of the new book.
    book = books.get_book(id)
    book.frontmatter["title"] = title or book.title
    book.frontmatter["owner"] = auth.logged_in().id
    book.write()

    return RedirectResponse(f"/book/{book}", status_code=HTTP.SEE_OTHER)


@rt("/{book:Book}", name="view")
def get(request, book: Book):
    "View book; contents list of sections and texts."
    auth.authorize(request, *book_view_rules, book=book)

    # Update the 'index.md' file, if any previous changes.
    book.write()

    menu = [
        A(Tx("Edit"), href=f"/edit/{id}"),
        A(Tx("Append"), href=f"/append/{id}/"),
        A(f'{Tx("Create")} {Tx("section")}', href=f"/section/{id}"),
        A(f'{Tx("Create")} {Tx("text")}', href=f"/text/{id}"),
        A(Tx("Recently modified"), href=f"/recent/{id}"),
        components.index_link(book),
        components.statuslist_link(book),
        components.refs_link(),
        A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/book/{book}.docx"),
        A(f'{Tx("Download")} {Tx("PDF file")}', href=f"/book/{book}.pdf"),
        A(f'{Tx("Download")} {Tx("TGZ file")}', href=f"/book/{book}.tgz"),
        A(Tx("Information"), href=f"/information/{id}"),
        A(Tx("State (JSON)"), href=f"/state/{id}"),
    ]
    if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
        menu.append(A(f'{Tx("Differences")}', href=f"/differences/{id}"))
    menu.append(A(f'{Tx("Copy")}', href=f"/copy/{id}"))
    menu.append(A(f'{Tx("Delete")}', href=f"/delete/{id}"))

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
        components.header(request, Tx("Contents"), book=book, menu=menu, status=book.status),
        Main(
            *segments,
            Div(NotStr(book.html)),
            Card(
                Div(A(Tx("Edit"), role="button", href=f"/edit/{id}")),
                Div(A(Tx("Append"), role="button", href=f"/append/{id}/")),
                cls="grid",
            ),
            cls="container",
        ),
        components.footer(book),
    )


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "View book text or section contents."
    if not path:
        return RedirectResponse(f"/book/{book}", status_code=HTTP.SEE_OTHER)

    auth.authorize(request, *book_view_rules, book=book)

    item = book[path]

    menu = []
    if item.parent:
        if item.parent.level == 0:  # Book.
            url = f"/book/{book}"
        else:
            url = f"/book/{book}/{item.parent.path}"
        menu.append(A(NotStr(f"&ShortUpArrow; {item.parent.title}"), href=url))
    if item.prev:
        url = f"/book/{book}/{item.prev.path}"
        menu.append(A(NotStr(f"&ShortLeftArrow; {item.prev.title}"), href=url))
    if item.next:
        url = f"/book/{book}/{item.next.path}"
        menu.append(A(NotStr(f"&ShortRightArrow; {item.next.title}"), href=url))

    menu.append(A(Tx("Edit"), href=f"/edit/{id}/{path}"))
    menu.append(A(Tx("Append"), href=f"/append/{id}/{path}"))

    if item.is_text:
        menu.append(A(Tx("Convert to section"), href=f"/to_section/{id}/{path}"))
        segments = [H3(item.heading)]

    elif item.is_section:
        menu.append(A(f'{Tx("Create")} {Tx("section")}', href=f"/section/{id}/{path}"))
        menu.append(A(f'{Tx("Create")} {Tx("text")}', href=f"/text/{id}/{path}"))
        segments = [
            Div(
                Div(H3(item.heading)),
                Div(components.search_form(f"/search/{id}/{path}")),
                cls="grid",
            ),
            toc(book, item.items),
        ]

    menu.append(components.index_link(book))
    menu.append(components.refs_link())
    menu.append(A(f'{Tx("Copy")}', href=f"/copy/{id}/{path}"))
    menu.append(A(f'{Tx("Delete")}', href=f"/delete/{id}/{path}"))

    if auth.authorized(request, *book_edit_rules, book=book):
        edit_buttons = Card(
            Div(A(Tx("Edit"), role="button", href=f"/edit/{id}/{path}")),
            Div(A(Tx("Append"), role="button", href=f"/append/{id}/{path}")),
            cls="grid",
        )
    else:
        edit_buttons = ""

    return (
        Title(item.title),
        components.header(request, item.title, book=book, menu=menu, status=item.status),
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
                    href=f"/backward/{book}/{item.path}",
                ),
                components.blank(0),
                A(
                    NotStr("&ShortDownArrow;"),
                    title=Tx("Forward"),
                    cls="plain",
                    href=f"/forward/{book}/{item.path}",
                ),
            ]
            if item.parent is not book:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortLeftArrow;"),
                        title=Tx("Out of"),
                        cls="plain",
                        href=f"/outof/{book}/{item.path}",
                    )
                )
            if item.prev_section:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortRightArrow;"),
                        title=Tx("Into"),
                        cls="plain",
                        href=f"/into/{book}/{item.path}",
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


@rt("/{book:Book}.docx", name="docx-download")
def get(request, book: Book):
    "Download the DOCX for the book. First get the parameters."
    auth.authorize(request, *book_view_rules, book=book)

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


@rt("/{book:Book}.docx", name="do-docx-download")
def post(request, book: Book, form: dict):
    "Actually download the DOCX file of the entire book."
    auth.authorize(request, *book_view_rules, book=book)

    settings = book.frontmatter.setdefault("docx", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["page_break_level"] = int(form["page_break_level"])
    settings["footnotes_location"] = form["footnotes_location"]
    settings["reference_font"] = form["reference_font"]
    settings["indexed_font"] = form["indexed_font"]

    # Save settings.
    if auth.authorized(request, *book_edit_rules, book=book):
        book.write()

    return Response(
        content=docx_creator.Creator(book, books.get_refs()).content(),
        media_type=constants.DOCX_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.docx"'},
    )


@rt("/{book:Book}.pdf", name="pdf-download")
def get(request, book: Book):
    "Download the PDF file for the book. First get the parameters."
    auth.authorize(request, *book_view_rules, book=book)

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


@rt("/{book:Book}.pdf", name="do-pdf-download")
def post(request, book: Book, form: dict):
    "Actually download the PDF file for the book."
    auth.authorize(request, *book_view_rules, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["page_break_level"] = form["page_break_level"]
    settings["contents_pages"] = form["contents_pages"]
    settings["contents_level"] = form["contents_level"]
    settings["footnotes_location"] = form["footnotes_location"]
    settings["indexed_xref"] = form["indexed_xref"]

    # Save settings.
    if auth.authorized(request, *book_edit_rules, book=book):
        book.write()

    return Response(
        content=pdf_creator.Creator(book, books.get_refs()).content(),
        media_type=constants.PDF_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.pdf"'},
    )


@rt("/{book:Book}.tgz", name="tgz-download")
def get(request, book: Book):
    "Download a gzipped tar file of the book."
    auth.authorize(request, *book_view_rules, book=book)

    filename = f"writethatbook_{book}_{utils.timestr(safe=True)}.tgz"

    return Response(
        content=book.get_tgzfile(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
