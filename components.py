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


def header(request, title, book=None, status=None, actions=None):
    "The standard page header with navigation bar."

    # General menu items.
    menu = [
        A(Tx("Books"), href="/"),
        A(Tx("References"), href="/refs"),
    ]

    # Links to pages for book.
    if book:
        if book is books.get_refs():
            menu.extend(
                [
                    A(Tx("Keywords"), href="/refs/keywords"),
                    A(Tx("Recently modified"), href="/refs/recent"),
                    A(Tx("Download TGZ file"), href="/refs/all.tgz"),
                ]
            )
        else:
            menu.extend(
                [
                    A(f'{Tx("Search in")} {Tx("book")}', href=f"/search/{book}"),
                    A(Tx("Index"), href=f"/meta/index/{book}"),
                    A(Tx("Recently modified"), href=f"/meta/recent/{book}"),
                    A(Tx("Status list"), href=f"/meta/status/{book}"),
                    A(Tx("Information"), href=f"/meta/info/{book}"),
                    A(Tx("Book state (JSON)"), href=f"/state/{book}"),
                    A(Tx("Download DOCX file"), href=f"/book/{book}.docx"),
                    A(Tx("Download PDF file"), href=f"/book/{book}.pdf"),
                    A(Tx("Download TGZ file"), href=f"/book/{book}.tgz"),
                ]
            )

    # Links to pages for admin.
    if auth.is_admin(request):
        menu.extend(
            [
                A(Tx("All users"), href="/user/list"),
                A(Tx("Download dump file"), href="/dump"),
                A(Tx("Site state (JSON)"), href="/state"),
                A(Tx("System"), href="/meta/system"),
            ]
        )

    # Links to general pages.
    menu.append(A(Tx("Software"), href="/meta/software"))

    if actions:
        actions = [A(NotStr(Tx(text)), href=href) for text, href in actions]
    else:
        actions = []
    if auth.is_admin(request):
        actions.append(A(Tx("Login"), href="/user/login"))

    # The first navbar item:
    # - Pulldown for links to pages.
    # - Pulldown for actions, if any.
    # - Link to book, if any.
    # - Title of page.
    style = "background: white; padding: 4px;"
    items = [
        Li(
            Details(
                Summary(
                    Img(src="/writethatbook.png", style=style),
                    role="button",
                    cls="outline",
                ),
                Ul(*[Li(a) for a in menu]),
                cls="dropdown",
            ),
        )
    ]
    if actions:
        items.append(
            Li(
                Details(
                    Summary(Img(src="/actions.svg", style=style)),
                    Ul(*[Li(a) for a in actions]),
                    cls="dropdown",
                ),
            )
        )
    if book:
        if book is books.get_refs():
            items.append(Li(A(Tx("References"), href="/refs")))
        else:
            items.append(Li(A(book.title, href=f"/book/{book}")))
    # The title of the page.
    items.append(Li(Strong(title)))

    navs = [Ul(*items)]

    # The second navbar item: login button, if not logged in.
    if auth.logged_in(request) is None:
        navs.append(Ul(Li(A(Tx("Login"), href="/user/login", role="button"))))

    # Set the color of the nav frame.
    nav_style = "outline-color: {color}; outline-width:8px; outline-style:solid; padding:0px 10px; border-radius:5px;"
    if status:
        nav_style = nav_style.format(color=status.color)
    else:
        nav_style = nav_style.format(color="black")
    return Header(Nav(*navs, style=nav_style), cls="container")


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
