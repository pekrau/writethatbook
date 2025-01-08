"Book, section and text view pages."

import os

from fasthtml.common import *

import auth
import books
from books import Book
import components
import constants
import docx_creator
from errors import *
import markdown
import pdf_creator
import users
import utils
from utils import Tx


class BookConvertor(Convertor):
    regex = "[^_./][^./]*"

    def convert(self, value: str) -> Book:
        return books.get_book(value)

    def to_string(self, value: Book) -> str:
        return value.id


register_url_convertor("Book", BookConvertor())


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Create a book or upload it from a gzipped tar file."
    auth.authorize(request, *auth.book_create_rules)
    title = Tx("Create or upload book")
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("Title"), components.required()),
                    Input(name="title", required=True, autofocus=True),
                ),
                Fieldset(
                    Legend(Tx("Upload TGZ file (optional)")),
                    Input(type="file", name="tgzfile"),
                ),
                components.save_button("Create"),
                action="/book",
                method="post",
            ),
            components.cancel_button("/"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/")
async def post(request, title: str, tgzfile: UploadFile):
    "Actually create a book or upload it from a gzipped tar file."
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
        raise Error(f"book '{book}' already exists", HTTP.CONFLICT)

    content = await tgzfile.read()
    if content:
        books.unpack_tgz_content(dirpath, content)
    else:  # Just create the directory; no content.
        dirpath.mkdir()

    # Re-read all books, ensuring everything is up to date.
    books.read_books()
    # Set the title and owner of the new book.
    book = books.get_book(id)
    book.title = title or book.title
    book.owner = str(auth.logged_in(request))
    book.write()

    return components.redirect(f"/book/{book}")


@rt("/{book:Book}")
def get(request, book: Book):
    "Display book; contents list of sections and texts."
    auth.authorize(request, *auth.book_view_rules, book=book)

    if auth.authorized(request, *auth.book_edit_rules, book=book):
        actions = [
            ("Edit", f"/edit/{book}"),
            ("Append", f"/mod/append/{book}/"),
            ("Copy", f"/copy/{book}"),
            ("Reread book", f"/reread/{book}"),
            ("Delete", f"/delete/{book}"),
        ]

        buttons = [
            Div(
                A(
                    Tx("Edit"),
                    href=f"/edit/{book}",
                    role="button",
                    style="width: 10em;",
                ),
            ),
            Div(
                A(
                    Tx("Append"),
                    href=f"/mod/append/{book}",
                    role="button",
                    style="width: 10em;",
                ),
            ),
        ]
        for type in [constants.SECTION, constants.TEXT]:
            buttons.append(
                Div(
                    Details(
                        Summary(Tx(f"Create {type}"), role="button", cls="secondary"),
                        Form(
                            Hidden(name="type", value=type),
                            Input(name="title", required=True, placeholder=Tx("Title")),
                            components.save_button("Create"),
                            action=f"/book/{book}/",  # Yes, trailing '/'; empty path string.
                            method="post",
                        ),
                    ),
                )
            )
        button_card = Card(*buttons, cls="grid")
        html = markdown.convert_to_html(book, book.content, href=f"/edit/{book}")

    else:
        actions = []
        button_card = ""
        html = book.html

    if auth.authorized(request, *auth.book_diff_rules, book=book):
        actions.append(["Differences", f"/diff/{book}"])

    segments = [components.search_form(f"/search/{book}")]

    if len(book.items) == 0:
        segments.append(H3(book.title))
        if book.subtitle:
            segments.append(H4(book.subtitle))
        for author in book.authors:
            segments.append(H5(author))
    else:
        segments.append(
            toc(
                book,
                book.items,
                edit=auth.authorized(request, *auth.book_edit_rules, book=book),
            )
        )

    title = Tx("Contents")
    if book.public:
        title += "; " + Tx("public")
    return (
        Title(book.title),
        components.header(
            request,
            title,
            book=book,
            status=book.status,
            actions=actions,
        ),
        Main(
            *segments,
            Div(NotStr(html)),
            button_card,
            cls="container",
        ),
        components.footer(request, book),
    )


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str):
    "Display text or section contents."
    auth.authorize(request, *auth.book_view_rules, book=book)
    if not path:
        return components.redirect(f"/book/{book}")

    item = book[path]

    neighbours = []
    style = "text-align: center;"
    kwargs = {"role": "button", "cls": "outline thin-button"}
    if item.prev:
        label = NotStr(f"&ShortLeftArrow; {item.prev.title}")
        url = f"/book/{book}/{item.prev.path}"
        neighbours.append(Div(A(label, href=url, **kwargs), style=style))
    else:
        neighbours.append(Div())
    label = NotStr(f"&ShortUpArrow; {item.parent.title}")
    if item.parent.level == 0:  # Book.
        url = f"/book/{book}"
    else:
        url = f"/book/{book}/{item.parent.path}"
    neighbours.append(Div(A(label, href=url, **kwargs), style=style))
    if item.next:
        label = NotStr(f"&ShortRightArrow; {item.next.title}")
        url = f"/book/{book}/{item.next.path}"
        neighbours.append(Div(A(label, href=url, **kwargs), style=style))
    else:
        neighbours.append(Div())

    if auth.authorized(request, *auth.book_edit_rules, book=book):
        actions = [
            ("Edit", f"/edit/{book}/{path}"),
            ("Append", f"/mod/append/{book}/{path}"),
        ]
        kwargs = {"role": "button", "style": "width: 10em;"}
        buttons = [
            Div(A(Tx("Edit"), href=f"/edit/{book}/{path}", **kwargs)),
            Div(A(Tx("Append"), href=f"/mod/append/{book}/{path}", **kwargs)),
        ]

        if item.is_text:
            actions.append(["Split", f"/mod/split/{book}/{path}"])
            buttons.append(Div())
            buttons.append(Div())
        elif item.is_section:
            actions.append(["Merge", f"/mod/merge/{book}/{path}"])
            for type in [constants.SECTION, constants.TEXT]:
                buttons.append(
                    Div(
                        Details(
                            Summary(
                                Tx(f"Create {type}"), role="button", cls="secondary"
                            ),
                            Form(
                                Hidden(name="type", value=type),
                                Input(
                                    name="title", required=True, placeholder=Tx("Title")
                                ),
                                components.save_button("Create"),
                                action=f"/book/{book}/{path}",
                                method="post",
                            ),
                        ),
                    )
                )

        actions.extend(
            [
                ("Reread book", f"/reread/{book}?path={path}"),
                ("Copy", f"/copy/{book}/{path}"),
                ("Delete", f"/delete/{book}/{path}"),
            ]
        )
        button_card = Card(*buttons, cls="grid")
        html = markdown.convert_to_html(
            item.book, item.content, href=f"/edit/{book}/{path}"
        )
    else:
        actions = []
        button_card = ""
        html = item.html

    segments = [Div(*neighbours, style="padding-bottom: 1em;", cls="grid")]
    if item.is_text:
        segments.append(H3(item.heading))
        if item.subtitle:
            segments.append(H5(item.subtitle))
    elif item.is_section:
        segments.append(
            Div(
                Div(H3(item.heading)),
                Div(components.search_form(f"/search/{book}/{path}")),
                cls="grid",
            )
        )
        if item.subtitle:
            segments.append(H5(item.subtitle))
        segments.append(
            toc(
                book,
                item.items,
                edit=auth.authorized(request, *auth.book_edit_rules, book=book),
            )
        )

    return (
        Title(item.title),
        components.header(
            request,
            item.title,
            book=book,
            status=item.status,
            actions=actions,
        ),
        Main(
            *segments,
            Div(NotStr(html), style="margin-top: 1em;"),
            button_card,
            cls="container",
        ),
        components.footer(request, item),
    )


@rt("/{book:Book}/{path:path}")
def post(request, book: Book, path: str, form: dict):
    "Create and add item (text or section)."
    auth.authorize(request, *auth.book_edit_rules, book=book)

    if path == "":
        parent = None
    else:
        parent = book[path]
        if not parent.is_section:
            raise Error("Cannot create text or section in non-section.")
    if not form.get("title"):
        raise Error("No title given.")

    if form["type"] == constants.TEXT:
        new = book.create_text(form["title"], parent=parent)
    elif form["type"] == constants.SECTION:
        new = book.create_section(form["title"], parent=parent)

    # Reread the book, ensuring everything is up to date.
    book.write()
    book.read()

    return components.redirect(f"/edit/{book}/{new.path}")


def toc(book, items, toplevel=True, edit=False):
    "Recursive lists of sections and texts."
    parts = []
    for item in items:
        if edit:
            arrows = [
                components.blank(0),
                A(
                    NotStr("&ShortUpArrow;"),
                    title=Tx("Backward"),
                    cls="plain-text",
                    href=f"/move/backward/{book}/{item.path}",
                ),
                components.blank(0),
                A(
                    NotStr("&ShortDownArrow;"),
                    title=Tx("Forward"),
                    cls="plain-text",
                    href=f"/move/forward/{book}/{item.path}",
                ),
            ]
            if not toplevel and item.parent is not book:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortLeftArrow;"),
                        title=Tx("Out of"),
                        cls="plain-text",
                        href=f"/move/outof/{book}/{item.path}",
                    )
                )
            if item.prev_section:
                arrows.append(components.blank(0))
                arrows.append(
                    A(
                        NotStr("&ShortRightArrow;"),
                        title=Tx("Into"),
                        cls="plain-text",
                        href=f"/move/into/{book}/{item.path}",
                    )
                )
        else:
            arrows = []
        if arrows:
            arrows.append(components.blank(0))
        parts.append(
            Li(
                *arrows,
                A(
                    item.title,
                    style=f"color: {item.status.color};",
                    href=f"/book/{item.book}/{item.path}",
                    title=f"{Tx(item.status)} {Tx(item.type)}",
                ),
                components.blank(0.2),
                item.subtitle or "",
            )
        )
        if item.is_section:
            parts.append(toc(book, item.items, toplevel=False, edit=edit))
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
                components.save_button("Download DOCX file"),
                action=f"/book/{book}.docx",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
        components.footer(request, book),
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
        ),
    ]

    title = f'{Tx("Download")} {Tx("PDF file")}'
    return (
        Title(title),
        components.header(request, title, book=book, status=book.status),
        Main(
            Form(
                *fields,
                components.save_button("Download PDF file"),
                action=f"/book/{book}.pdf",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
        components.footer(request, book),
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
        content=book.get_tgz_content(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def get_books_table(request, books):
    "Return a table containing the given books."
    rows = []
    for book in books:
        owner = users.get(book.owner)
        if auth.authorized(request, *auth.user_view_rules, user=owner):
            owner = A(owner.name or owner.id, href=f"/user/view/{owner}")
        else:
            owner = owner.name or owner.id
        rows.append(
            Tr(
                Td(A(book.title, href=f"/book/{book.id}")),
                Td(Tx(book.type.capitalize())),
                Td(Tx(book.status)),
                Td(Tx(components.thousands(book.sum_characters))),
                Td(owner),
                Td(Tx(book.public and "Yes" or "No")),
                Td(book.modified),
            )
        )
    if rows:
        return Table(
            Thead(
                Tr(
                    Th(Tx("Title")),
                    Th(Tx("Type")),
                    Th(Tx("Status")),
                    Th(Tx("Characters")),
                    Th(Tx("Owner")),
                    Th(Tx("Public")),
                    Th(Tx("Modified")),
                )
            ),
            Tbody(*rows),
        )
    else:
        return I(Tx("No books"))
