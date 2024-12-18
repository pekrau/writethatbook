"Classes, functions and instances for access authorization."

from http import HTTPStatus as HTTP
import urllib

from icecream import ic
from json_logic import jsonLogic
from fasthtml.common import Response, RedirectResponse, uri

import constants
import users


class NotAllowed(Exception):
    "Custom exception for when not allowed to access a resource."
    pass


def not_allowed_handler(request, exc):
    """If logged in, then forbidden since authorization failed.
    If not logged in, then redirect to login.
    """
    ic("not_allowed_handler")
    if request.scope.get("current_user"):
        return Response(content="Forbidden", status_code=HTTP.FORBIDDEN)
    else:
        path = urllib.parse.urlencode({"path": request.url.path})
        return RedirectResponse(f"/user/login?{path}", status_code=HTTP.SEE_OTHER)


def authorized(request, *rules, **context):
    """Check each rule in turn.
    Return True if the rule applies and allows access.
    Return False if the rule applies and denies access.
    Return False if no rule applies.
    """
    context["current_user"] = request.scope.get("current_user")
    context["constants"] = constants
    for rule in rules:
        result = rule.apply(**context)
        if result is not None:
            return result
    return False


def authorize(request, *rules, **context):
    """Check each rule in turn.
    Simply return if the rule applies and allows access.
    Raise NotAllowed if the rule applies and denies access.
    Raise NotAllowed if no rule applies.
    """
    if not authorized(request, *rules, **context):
        raise NotAllowed

def allow_all(request):
    "For clarity, or placeholder."
    pass

def allow_admin(request):
    "Does the current user have role 'admin'?"
    authorize(request,
              Allow(
                  {
                      "and": [
                          {"!!": {"var": "current_user"}},
                          {"==": [{"var": "current_user.role"}, {"var": "constants.ADMIN_ROLE"}]},
                      ]
                  }
              )
              )

def logged_in(request):
    "Return the current user (logged in)."
    return request.scope.get("current_user")


def is_admin(request):
    "Is the current user defined (logged in) and has the role 'admin'?"
    try:
        return request.scope["current_user"].role == constants.ADMIN_ROLE
    except KeyError:
        return False


class Allow:
    "Allow access if the rule evaluates to True."

    def __init__(self, logic):
        self.logic = logic

    def apply(self, **context):
        "Return None if rule does not apply, True of allowed, False if denied."
        if jsonLogic(self.logic, context):
            return True


class Deny:
    "Deny access if the rule evaluates to True."

    def __init__(self, logic):
        self.logic = logic

    def apply(self, **context):
        "Return None if rule does not apply, True of allowed, False if denied."
        if jsonLogic(self.logic, context):
            return False
