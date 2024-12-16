"User HTTP resources."

from http import HTTPStatus as HTTP

from icecream import ic
from fasthtml.common import *

import auth
import components
import constants
import users
from utils import Tx, Error


class UserConvertor(Convertor):
    regex = "[a-zA-Z][a-zA-Z0-9-_]*"

    def convert(self, value: str) -> users.User:
        return users.database[value]

    def to_string(self, value: users.User) -> str:
        return value.id


register_url_convertor("User", UserConvertor())


app, rt = fast_app(
    live="WRITETHATBOOK_DEVELOPMENT" in os.environ, before=users.set_current_user
)


@rt("/list", name="list")
def get(request):
    "Display a list of all users."
    auth.authorize(request, auth.allow_admin)
    rows = []
    for user in users.database.all():
        rows.append(
            Tr(
                Td(A(user.id, href=f"/user/view/{user.id}")),
                Td(user.name or "-"),
                Td(user.role),
            )
        )
    title = Tx("All users")
    return (
        Title(title),
        components.header(
            request, title, menu=[A(Tx("Create user"), href="/user/create")]
        ),
        Main(
            Table(
                Thead(Tr(Th(Tx("User"), scope="col"), Th(Tx("Name")), Th(Tx("Role")))),
                Tbody(*rows),
            ),
            cls="container",
        ),
    )


@rt("/view/{user:User}", name="view")
def get(request, user: users.User):
    "User account page."
    auth.authorize(
        request,
        auth.deny_anonymous,
        auth.Allow({"==": [{"var": "current_user"}, {"var": "user"}]}),
        auth.allow_admin,
        user=user,
    )
    title = f'{Tx("User")} {user}'
    menu = []
    if auth.logged_in(request) is user:
        menu.append(A(Tx("Logout"), href="/user/logout"))
    if auth.is_admin(request):
        menu.append(A(Tx("All users"), href="/user/list"))
    return (
        Title(title),
        components.header(request, title, menu=menu),
        Main(
            Table(
                Tr(Td(Tx("Identifier")), Td(user.id)),
                Tr(Td(Tx("Role")), Td(user.role)),
                Tr(Td(Tx("Name")), Td(user.name or "-")),
                Tr(Td(Tx("Email")), Td(user.email or "-")),
                Tr(Td(Tx("API key")), Td(user.apikey or "-")),
                Tr(Td(Tx("Code")), Td(user.code or "-")),
            ),
            Div(
                Div(A(Tx("Edit"), role="button", href=f"/user/edit/{user.id}")),
                cls="grid",
            ),
            cls="container",
        ),
    )


@rt("/edit/{user:User}", name="edit")
def get(request, user: users.User):
    "Form page for editing a user account."
    auth.authorize(
        request,
        auth.deny_anonymous,
        auth.Allow({"==": [{"var": "current_user"}, {"var": "user"}]}),
        auth.allow_admin,
        user=user,
    )
    fields = []
    if auth.logged_in(request) is not user and auth.is_admin(request):
        fields.append(
            Fieldset(
                Legend(Tx("Role")),
                Label(
                    Input(
                        type="radio",
                        name="role",
                        value=constants.ADMIN_ROLE,
                        checked=user.role == constants.ADMIN_ROLE,
                    ),
                    constants.ADMIN_ROLE,
                ),
                Label(
                    Input(
                        type="radio",
                        name="role",
                        value=constants.USER_ROLE,
                        checked=user.role == constants.USER_ROLE,
                    ),
                    constants.USER_ROLE,
                ),
            )
        )
    fields.append(
        Fieldset(
            Legend(Tx("Name")),
            Input(name="name", value=user.name or ""),
        )
    )
    fields.append(
        Fieldset(
            Legend(Tx("Email")),
            Input(type="email", name="email", value=user.email or ""),
        )
    )
    fields.append(
        Fieldset(
            Legend(Tx("API key")),
            Label(Input(type="checkbox", name="apikey"), Tx("Generate new value.")),
        )
    )
    if auth.logged_in(request) is user:
        fields.append(
            Fieldset(
                Legend(Tx("Password")),
                Input(
                    type="password", name="old_password", placeholder=Tx("Old password")
                ),
                Input(
                    type="password", name="new_password", placeholder=Tx("New password")
                ),
            )
        )
    elif auth.is_admin(request):
        fields.append(
            Fieldset(
                Legend(Tx("Password")),
                Input(type="checkbox", name="code"),
                Tx("Require new value."),
            )
        )

    title = f'{Tx("Edit")} {user}'
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                *fields,
                Button(Tx("Save")),
                action=f"/user/edit/{user.id}",
                method="post",
            ),
            components.cancel_button(f"/user/view/{user.id}"),
            cls="container",
        ),
    )


@rt("/edit/{user:User}", name="do_edit")
def post(request, user: users.User, form: dict):
    "Actually edit the user account."
    auth.authorize(
        request,
        auth.deny_anonymous,
        auth.Allow({"==": [{"var": "current_user"}, {"var": "user"}]}),
        auth.allow_admin,
        user=user,
    )
    with users.database:
        if auth.logged_in(request) is not user and auth.is_admin(request):
            if form.get("role") in constants.ROLES:
                user.role = form["role"]
        user.email = form.get("email") or None
        user.name = form.get("name") or None
        if form.get("apikey"):
            user.set_apikey()
        if auth.is_admin(request) and form.get("code"):
            user.reset_password()
        if auth.logged_in(request) is user:
            old_password = form.get("old_password")
            new_password = form.get("new_password")
            if old_password and new_password and user.login(old_password):
                user.set_password(new_password)
        ic(user.name)
    return RedirectResponse(f"/user/view/{user.id}", status_code=HTTP.SEE_OTHER)


@rt("/create", name="create")
def get(request):
    "Form page for creating a new user account."
    auth.authorize(request, auth.allow_admin)
    title = Tx("Create user")
    return (
        Title(title),
        components.header(request, title, menu=[A(Tx("All users"), href="/user/list")]),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("Identifier")),
                    Input(name="userid", required=True, autofocus=True),
                ),
                Fieldset(
                    Legend(Tx("Role")),
                    Label(
                        Input(type="radio", name="role", value=constants.ADMIN_ROLE),
                        constants.ADMIN_ROLE,
                    ),
                    Label(
                        Input(
                            type="radio",
                            name="role",
                            value=constants.USER_ROLE,
                            checked=True,
                        ),
                        constants.USER_ROLE,
                    ),
                ),
                Fieldset(
                    Legend(Tx("Name")),
                    Input(name="name"),
                ),
                Fieldset(Legend(Tx("Email")), Input(type="email", name="email")),
                Button(Tx("Create")),
                action="/user/create",
                method="post",
            ),
            cls="container",
        ),
    )


@rt("/create", name="do_create")
def post(request, form: dict):
    "Actually create a new user account."
    auth.authorize(request, auth.allow_admin)
    with users.database as database:
        user = database.create_user(form["userid"], role=form["role"])
        user.name = form.get("name") or None
        user.email = form.get("email") or None
        user.reset_password()
    return RedirectResponse(f"/user/view/{user.id}", status_code=HTTP.SEE_OTHER)


@rt("/login", name="login")
def get(request, path: str = None):
    "Login page."
    if path:
        hidden = [Input(type="hidden", name="path", value=path)]
    else:
        hidden = []
    return Titled(
        f"{constants.SOFTWARE} login",
        Form(
            *hidden,
            Input(id="userid", placeholder=Tx("User"), autofocus=True),
            Input(id="password", type="password", placeholder=Tx("Password")),
            Button(Tx("Login")),
            action="/user/login",
            method="post",
        ),
    )


@rt("/login", name="do_login")
def post(request, userid: str, password: str, path: str = None):
    "Actually do login."
    if not userid or not password:
        return RedirectResponse("/user/login", status_code=HTTP.SEE_OTHER)
    try:
        user = users.database[userid]
    except KeyError:
        return RedirectResponse("/login", status_code=HTTP.SEE_OTHER)
    if user.login(password):
        request.session["auth"] = user.id
        return RedirectResponse(path or "/", status_code=HTTP.SEE_OTHER)
    else:
        return RedirectResponse("/user/login", status_code=HTTP.SEE_OTHER)


@rt("/logout", name="logout")
def get(request):
    "Perform logout."
    request.session.pop("auth", None)
    return RedirectResponse("/", status_code=HTTP.SEE_OTHER)
