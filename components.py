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


def search_form(action, term=None, autofocus=False):
    return Form(
        Input(
            name="term",
            type="search",
            placeholder=f'{Tx("Search in")} {Tx("book")}',
            value=term,
            autofocus=autofocus,
        ),
        Input(type="submit", value=Tx("Search")),
        style="margin-bottom: 0;",
        role="search",
        action=action,
        method="post",
    )


def header(request, title, book=None, status=None, tools=None, search=True):
    "The standard page header with navigation bar."

    # General menu items.
    menu = [
        A(Tx("Books"), href="/"),
        A(Tx("References"), href="/refs"),
    ]

    # Links to pages for book.
    if book:
        if book is books.get_refs():
            if search:
                menu.append(A(f'{Tx("Search in")} {Tx("references")}', href="/refs/search"))
            menu.extend(
                [
                    A(Tx("Keywords"), href="/refs/keywords"),
                    A(Tx("Recently modified"), href="/refs/recent"),
                    A(Tx("Download TGZ file"), href="/refs/all.tgz"),
                ]
            )
        else:
            if search:
                menu.append(A(f'{Tx("Search in")} {Tx("book")}', href=f"/search/{book}"))
            menu.extend(
                [
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

    if tools:
        tools = [A(NotStr(Tx(text)), href=href) for text, href in tools]
        if auth.is_admin(request):
            tools.append(A(Tx("Login"), href=f"/user/login?path={request.url.path}"))
    else:
        tools = []

    # The first navbar item:
    # - Pulldown for links to pages.
    # - Pulldown for tools, if any.
    # - Link to book, if any.
    # - Title of page.
    style = "background: white; padding: 4px;"
    items = [
        Li(
            Details(
                Summary(
                    Img(src="/writethatbook.png", style=style),
                    title=Tx("Pages"),
                    role="button",
                    cls="outline",
                ),
                Ul(*[Li(a) for a in menu]),
                cls="dropdown",
            ),
        )
    ]
    if tools:
        items.append(
            Li(
                Details(
                    Summary(Img(src="/tools.svg", title=Tx("Tools"), style=style)),
                    Ul(*[Li(a) for a in tools]),
                    cls="dropdown",
                ),
            )
        )
    if book:
        if book is books.get_refs():
            items.append(Li(A(Tx("References"), href="/refs")))
        else:
            items.append(Li(A(book.title, title=Tx("Book"), href=f"/book/{book}")))
    # The title of the page.
    items.append(Li(Strong(title)))

    navs = [Ul(*items)]

    # Search field, if book is defined.
    if search and book:
        if book is books.get_refs():
            navs.append(Ul(Li(search_form("/refs/search"))))
        else:
            navs.append(Ul(Li(search_form(f"/search/{book}"))))

    # Login button, if not logged in.
    if auth.logged_in(request) is None:
        navs.append(
            Ul(
                Li(
                    A(
                        Tx("Login"),
                        href=f"/user/login?path={request.url.path}",
                        role="button",
                    )
                )
            )
        )

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
