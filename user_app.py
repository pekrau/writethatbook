"User resources."

from fasthtml.common import *

import auth
import components
import constants
from errors import *
import users
import utils
from utils import Tx


class UserConvertor(Convertor):
    regex = "[a-zA-Z][a-zA-Z0-9-_]*"

    def convert(self, value: str) -> users.User:
        return users.database[value]

    def to_string(self, value: users.User) -> str:
        return value.id


register_url_convertor("User", UserConvertor())


app, rt = utils.get_fast_app()


@rt("/")
def get(request):
    "Form page for creating a new user account."
    auth.allow_admin(request)
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
                action="/user/",
                method="post",
            ),
            components.cancel_button("/user/list"),
            cls="container",
        ),
    )


@rt("/")
def post(request, form: dict):
    "Actually create a new user account."
    auth.allow_admin(request)
    with users.database as database:
        user = database.create_user(form["userid"], role=form["role"])
        user.name = form.get("name") or None
        user.email = form.get("email") or None
        user.reset_password()
    return utils.redirect(f"/user/view/{user}")


@rt("/list")
def get(request):
    "View the list of all users."
    auth.allow_admin(request)
    rows = []
    for user in users.database.all():
        rows.append(
            Tr(
                Td(A(user.id, href=f"/user/view/{user}")),
                Td(user.name or "-"),
                Td(user.role),
            )
        )
    title = Tx("All users")
    return (
        Title(title),
        components.header(
            request, title, menu=[A(Tx("Create user"), href="/user/")]
        ),
        Main(
            Table(
                Thead(Tr(Th(Tx("User"), scope="col"), Th(Tx("Name")), Th(Tx("Role")))),
                Tbody(*rows),
            ),
            cls="container",
        ),
    )


@rt("/view/{user:User}")
def get(request, user: users.User):
    "User account page."
    auth.authorize(request, *auth.user_view_rules, user=user)
    title = f'{Tx("User")} {user}'
    if auth.logged_in(request) is user:
        logout = Form(Button("Logout"),
                      action="/user/logout",
                      method="post")
    else:
        logout = ""
    menu = []
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
            Card(
                Div(A(Tx("Edit"), role="button", href=f"/user/edit/{user}")),
                Div(logout),
                cls="grid"
            ),
            cls="container",
        ),
    )


@rt("/edit/{user:User}")
def get(request, user: users.User):
    "Form page for editing a user account."
    auth.authorize(request, *auth.user_edit_rules, user=user)
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
                action=f"/user/edit/{user}",
                method="post",
            ),
            components.cancel_button(f"/user/view/{user}"),
            cls="container",
        ),
    )


@rt("/edit/{user:User}")
def post(request, user: users.User, form: dict):
    "Actually edit the user account."
    auth.authorize(request, *auth.user_edit_rules, user=user)
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
    return utils.redirect(f"/user/view/{user}")


@rt("/login")
def get(request, path: str = None):
    "Login page. Also with forms for resetting and setting password."
    auth.allow_anyone(request)
    if path:
        hidden = [Input(type="hidden", name="path", value=path)]
    else:
        hidden = []
    title = "Login"
    return (
        Title(title),
        components.header(request, title),
        Main(
            Article(
                Form(
                H2("Login"),
                *hidden,
                Input(id="userid", placeholder=Tx("Identifier"), autofocus=True, required=True),
                Input(id="password", type="password", placeholder=Tx("Password"), required=True),
                Button("Login"),
                action="/user/login",
                method="post",
            )),
            Article(
            Form(
                H2(Tx("Reset password")),
                Input(id="userid", placeholder=Tx("Identifier")),
                Input(id="email", placeholder=Tx("Email")),
                Button(Tx("Reset password")),
                action="/user/reset",
                method="post",
            )),
            Article(
            Form(
                H2(Tx("Set password")),
                Input(id="userid", placeholder=Tx("Identifier"), required=True),
                Input(id="password", type="password", placeholder=Tx("Password"), required=True),
                Input(id="code", placeholder=Tx("Code"), required=True),
                Button(Tx("Set password")),
                action="/user/password",
                method="post",
            )),
            cls="container",
        )
    )


@rt("/login")
def post(request, userid: str, password: str, path: str = None):
    "Actually do login."
    auth.allow_anyone(request)
    if not userid or not password:
        add_toast(request.session, "Missing user identifier and/or password.", "error")
        return utils.redirect("/user/login")
    try:
        user = users.database[userid]
        if not user.login(password):
            raise KeyError
    except KeyError:
        add_toast(request.session, "Invalid user identifier and/or password.", "error")
        return utils.redirect("/user/login")
    request.session["auth"] = user.id
    return utils.redirect(path or "/")


@rt("/reset")
def post(request, form: dict):
    "Reset the password for an account."
    auth.allow_anyone(request)
    user = users.database.get(userid=form.get("userid"))
    if user is None:
        user = users.database.get(email=form.get("email"))
    if user:
        with users.database:
            user.reset_password()
    return utils.redirect("/")


@rt("/password")
def post(request, form: dict):
    "Set the password of a user account."
    auth.allow_anyone(request)
    try:
        user = users.database[form["userid"]]
        if not user.code:
            raise KeyError
        if user.code != form["code"]:
            raise KeyError
        if len(form["password"]) < constants.MIN_PASSWORD_LENGTH:
            raise KeyError
    except KeyError:
        add_toast(request.session, "Invalid user identifier, code or too short password.", "error")
        return utils.redirect("/user/login")
    with users.database:
        user.set_password(form["password"])
        user.code = None
    request.session["auth"] = user.id
    return utils.redirect(f"/user/view/{user}")


@rt("/logout")
def post(request):
    "Perform logout."
    request.session.pop("auth", None)
    return utils.redirect("/")
