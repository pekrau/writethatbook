"Page components and functions."

from http import HTTPStatus as HTTP
import string

from fasthtml.common import *

import auth
import books
import constants
import utils
from utils import Tx, Error


def blank(width, style=None):
    if isinstance(width, (int, float)):
        width = str(width) + "em"
    if style:
        style += f" padding: 0 {width};"
    else:
        style = f"padding: 0 {width};"
    return Span(NotStr("&nbsp;"), style=style)


def cancel_button(href):
    return Div(
        A(Tx("Cancel"), role="button", href=href, cls="outline secondary"),
        style="margin-top: 20px;",
    )


def search_form(action, term=None):
    return Form(
        Input(
            name="term",
            type="search",
            placeholder=Tx("Search"),
            value=term,
            autofocus=True,
        ),
        Input(type="submit", value=Tx("Search")),
        role="search",
        action=action,
        method="post",
    )


def header(request, title, book=None, status=None, actions=None, pages=None, menu=None):
    "The standard page header with navigation bar."

    # The first cell: icon link to home page, and title of book, if any.
    home = A(Img(src="/writethatbook.png", width=32, height=32), href="/", title=constants.SOFTWARE)
    if book:
        if book is books.get_refs():
            cells = [
                Ul(
                    Li(home),
                    Li(A(Strong(Tx("References")), href="/refs")),
                )
            ]
        else:
            cells = [
                Ul(
                    Li(home),
                    Li(A(Strong(book.title), href=f"/book/{book.id}")),
                )
            ]
    else:
        cells = [Ul(Li(home))]

    # The second cell: title.
    cells.append(Ul(Li(Strong(title))))

    # The third cell: login button and menus.
    items = []
    if auth.logged_in(request) is None:
        items.append(Li(A(Button("Login"), href="/user/login")))
    if actions:
        items.append(
            Li(
                Details(
                    Summary(Tx("Actions"),  style="width: 8em;"),
                    Ul(*[Li(A(NotStr(Tx(t)), href=h)) for t, h in actions]),
                    cls="dropdown",
                ),
            )
        )
    if pages:
        items.append(
            Li(
                Details(
                    Summary(Tx("Pages"), style="width: 8em;"),
                    Ul(*[Li(A(NotStr(Tx(t)), href=h)) for t, h in pages]),
                    cls="dropdown",
                ),
            )
        )
    if menu:
        items.append(
            Li(
                Details(
                    Summary(Tx("Menu"), style="width: 10em;"),
                    Ul(*[Li(i) for i in menu]),
                    cls="dropdown",
                ),
            )
        )
    cells.append(Ul(*items))

    # Set the color of the nav frame.
    nav_style = "outline-color: {color}; outline-width:8px; outline-style:solid; padding:0px 10px; border-radius:5px;"
    if status:
        nav_style = nav_style.format(color=status.color)
    else:
        nav_style = nav_style.format(color="black")
    return Header(Nav(*cells, style=nav_style), cls="container")


def footer(item):
    return Footer(
        Hr(),
        Div(
            Div(Tx(item.status)),
            Div(item.modified),
            Div(
                f'{utils.thousands(item.n_words)} {Tx("words")}; ',
                f'{utils.thousands(item.n_characters)} {Tx("characters")}',
            ),
            cls="grid"),
        cls="container",
    )


def get_status_field(item):
    "Return select input field for status."
    status_options = []
    for status in constants.STATUSES:
        if item.status == status:
            status_options.append(
                Option(Tx(str(status)), selected=True, value=repr(status))
            )
        else:
            status_options.append(Option(Tx(str(status)), value=repr(status)))
    return Select(*status_options, name="status", required=True)


def required():
    return Span(NotStr("&nbsp;*"), style="color: red")
