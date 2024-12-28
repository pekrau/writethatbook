"FastHTML components and functions."

import os
import string

from fasthtml.common import *

import auth
import books
import constants
from errors import *
import users
import utils
from utils import Tx


def get_fast_app(routes=None):
    app, rt = fast_app(
        live="WRITETHATBOOK_DEVELOPMENT" in os.environ,
        static_path="static",
        before=users.set_current_user,
        hdrs=(Link(rel="stylesheet", href="/mods.css", type="text/css"),),
        exception_handlers={
            Error: error_handler,
            NotAllowed: not_allowed_handler,
        },
        routes=routes,
    )
    setup_toasts(app)
    return app, rt


def redirect(href):
    "Redirect with the usually more appropriate 303 status code."
    return RedirectResponse(href, status_code=HTTP.SEE_OTHER)


def blank(width, style=None):
    if isinstance(width, (int, float)):
        width = str(width) + "em"
    if style:
        style += f" padding: 0 {width};"
    else:
        style = f"padding: 0 {width};"
    return Span(NotStr("&nbsp;"), style=style)


def save_button(text="Save"):
    return Button(Tx(text), style="width: 10em;")


def cancel_button(href):
    return Div(
        A(
            Tx("Cancel"),
            role="button",
            href=href,
            cls="outline secondary",
            style="width: 10em;",
        ),
        style="margin-top: 1em;",
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
    home = A(
        Img(src="/writethatbook.png", style="background-color: white; padding: 2px;"),
        href="/",
        role="button",
        title=f"{constants.SOFTWARE} {constants.__version__}",
        cls="outline contrast",
    )
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
                    Summary(Tx("Actions"), style="width: 7em;"),
                    Ul(*[Li(A(NotStr(Tx(t)), href=h)) for t, h in actions]),
                    cls="dropdown",
                ),
            )
        )
    if pages:
        items.append(
            Li(
                Details(
                    Summary(Tx("Pages"), style="width: 7em;"),
                    Ul(*[Li(A(NotStr(Tx(t)), href=h)) for t, h in pages]),
                    cls="dropdown",
                ),
            )
        )
    if menu:
        items.append(
            Li(
                Details(
                    Summary(Tx("Menu"), style="width: 7em;"),
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


def footer(request, item=None):
    if item:
        cells = [
            Div(Tx(item.status), title=Tx("Status")),
            Div(item.modified, title=Tx("Modified")),
        ]
        if item.type in (constants.BOOK, constants.SECTION):
            cells.append(
                Div(
                    f'{thousands(item.sum_words)} {Tx("words")}; ',
                    f'{thousands(item.sum_characters)} {Tx("characters")}',
                    " (",
                    f'{thousands(item.n_words)} {Tx("words")}; ',
                    f'{thousands(item.n_characters)} {Tx("characters")}',
                    ")",
                )
            )
        else:
            cells.append(
                Div(
                    f'{thousands(item.n_words)} {Tx("words")}; ',
                    f'{thousands(item.n_characters)} {Tx("characters")}',
                )
            )

    else:
        cells = [Div(), Div(), Div()]
    user = auth.logged_in(request)
    if user:
        if auth.authorized(request, *auth.user_view_rules, user=user):
            cells.append(
                Div(
                    A(user.name or user.id, href=f"/user/view/{user.id}"),
                    title=Tx("Logged in"),
                    style="text-align: right;",
                )
            )
        else:
            cells.append(Div(user.name or user.id), style="text-align: right;")
    else:
        cells.append(Div())

    return Footer(
        Hr(),
        Div(*cells, cls="grid"),
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


def thousands(i):
    return f"{i:,}".replace(",", ".")
