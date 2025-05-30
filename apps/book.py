"Book, section and text view pages."

import os

from fasthtml.common import *

import auth
import books
from books import Book
import components
import constants
from errors import *
import markdown
import users
import utils
from utils import Tx


class BookConvertor(Convertor):
    regex = "[^_./][^./]*"

    def convert(self, value: str) -> books.Book:
        return books.get_book(value)

    def to_string(self, value: books.Book) -> str:
        return value.id


register_url_convertor("Book", BookConvertor())


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Create a book or upload it from a gzipped tar file."
    auth.authorize(request, *auth.book_create)
    title = Tx("Create or upload book")
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                Fieldset(
                    Label(Tx("Title"), components.required()),
                    Input(name="title", required=True, autofocus=True),
                ),
                Fieldset(
                    Label(Tx("Upload TGZ file (optional)")),
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
    auth.authorize(request, *auth.book_create)
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
def get(request, book: Book, position: int = None):
    "Display book; contents list of sections and texts."
    auth.authorize(request, *auth.book_view, book=book)

    if auth.authorized(request, *auth.book_edit, book=book):
        tools = [
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
        html = markdown.to_html(
            book.content, book=book, position=position, edit_href=f"/edit/{book}"
        )

    else:
        tools = []
        button_card = ""
        html = markdown.to_html(book.content, book=book)

    if auth.authorized(request, *auth.book_diff, book=book):
        tools.append(["Differences", f"/diff/{book}"])

    segments = []

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
                edit=auth.authorized(request, *auth.book_edit, book=book),
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
            tools=tools,
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
def get(request, book: Book, path: str, position: int = None):
    "Display text or section contents."
    auth.authorize(request, *auth.book_view, book=book)
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

    if auth.authorized(request, *auth.book_edit, book=book):
        tools = [
            ("Edit", f"/edit/{book}/{path}"),
            ("Append", f"/mod/append/{book}/{path}"),
        ]
        kwargs = {"role": "button", "style": "width: 10em;"}
        buttons = [
            Div(A(Tx("Edit"), href=f"/edit/{book}/{path}", **kwargs)),
            Div(A(Tx("Append"), href=f"/mod/append/{book}/{path}", **kwargs)),
        ]

        if item.is_text:
            tools.append(["Split", f"/mod/split/{book}/{path}"])
            buttons.append(Div())
            buttons.append(Div())
        elif item.is_section:
            tools.append(["Merge", f"/mod/merge/{book}/{path}"])
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

        tools.extend(
            [
                ("Reread book", f"/reread/{book}?path={path}"),
                ("Copy", f"/copy/{book}/{path}"),
                ("Delete", f"/delete/{book}/{path}"),
            ]
        )
        button_card = Card(*buttons, cls="grid")
        html = markdown.to_html(
            item.content,
            book=item.book,
            position=position,
            edit_href=f"/edit/{book}/{path}",
        )

    # Not authorized to edit.
    else:
        tools = []
        button_card = ""
        html = markdown.to_html(item.content, book=item.book)

    segments = [Div(*neighbours, style="padding-bottom: 1em;", cls="grid")]
    if item.is_text:
        segments.append(H3(item.heading))
        if item.subtitle:
            segments.append(H5(item.subtitle))
    elif item.is_section:
        segments.append(
            Div(
                Div(H3(item.heading)),
                cls="grid",
            )
        )
        if item.subtitle:
            segments.append(H5(item.subtitle))
        segments.append(
            toc(
                book,
                item.items,
                edit=auth.authorized(request, *auth.book_edit, book=book),
            )
        )

    return (
        Title(item.title),
        components.header(
            request,
            item.title,
            book=book,
            item=item,
            tools=tools,
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
    auth.authorize(request, *auth.book_edit, book=book)

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
                Img(
                    src="/folder.svg" if item.is_section else "/file-text.svg",
                    cls="white",
                    title=Tx(item.type.capitalize()),
                ),
                components.blank(0.1),
                A(
                    item.title,
                    style=f"color: {item.status.color};",
                    href=f"/book/{item.book}/{item.path}",
                    title=f'{Tx("Status")}: {Tx(item.status)}',
                ),
                components.blank(0.2),
                item.subtitle or "",
            )
        )
        if item.is_section:
            parts.append(toc(book, item.items, toplevel=False, edit=edit))
    return Ol(*parts)


def get_books_table(request, books):
    "Return a table containing the given books."
    rows = []
    for book in books:
        owner = users.get(book.owner)
        if auth.authorized(request, *auth.user_view, user=owner):
            owner = A(owner.name or owner.id, href=f"/user/view/{owner}")
        else:
            owner = owner.name or owner.id
        rows.append(
            Tr(
                Td(A(book.title, href=f"/book/{book.id}")),
                Td(Tx(book.type.capitalize())),
                Td(Tx(book.status)),
                Td(Tx(utils.numerical(book.sum_words)), cls="right"),
                Td(Tx(utils.numerical(book.sum_characters)), cls="right"),
                Td(owner),
                Td(Tx(book.public and "Yes" or "No")),
                Td(utils.str_datetime_display(book.modified)),
            )
        )
    if rows:
        return Table(
            Thead(
                Tr(
                    Th(Tx("Title")),
                    Th(Tx("Type")),
                    Th(Tx("Status")),
                    Th(Tx("Words"), cls="right"),
                    Th(Tx("Characters"), cls="right"),
                    Th(Tx("Owner")),
                    Th(Tx("Public")),
                    Th(Tx("Modified")),
                )
            ),
            Tbody(*rows),
        )
    else:
        return I(Tx("No books"))
