"Classes, functions and instances for access authorization."

import os

import json_logic

import constants
from errors import *
import users


def authorized(request, *rules, **context):
    """Check each rule in turn.
    Return True if the rule applies and allows access.
    Return False if the rule applies and denies access.
    Return False if no rule applies.
    """
    context["environ"] = os.environ
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


def allow_anyone(request):
    "For clarity."
    pass


def allow_logged_in(request):
    "Do not allow anonymous users."
    authorize(request, Allow({"bool": {"var": "current_user"}}))


def allow_admin(request):
    "Does the current user have role 'admin'?"
    authorize(
        request,
        Allow(
            {
                "and": [
                    {"bool": {"var": "current_user"}},
                    {
                        "==": [
                            {"var": "current_user.role"},
                            {"var": "constants.ADMIN_ROLE"},
                        ]
                    },
                ]
            }
        ),
    )


def logged_in(request):
    "Return the current user (logged in)."
    return request.scope.get("current_user")


def is_admin(request):
    "Is the current user defined (logged in) and has the role 'admin'?"
    try:
        return request.scope["current_user"].is_admin
    except KeyError:
        return False


class Allow:
    "Allow access if the rule evaluates to True."

    def __init__(self, logic):
        self.logic = logic

    def apply(self, **context):
        "Return None if rule does not apply, True of allowed, False if denied."
        if json_logic.evaluate(self.logic, context):
            return True
        return None


class Deny:
    "Deny access if the rule evaluates to True."

    def __init__(self, logic):
        self.logic = logic

    def apply(self, **context):
        "Return None if rule does not apply, True of allowed, False if denied."
        if json_logic.evaluate(self.logic, context):
            return False
        return None


# Access rule sets.
user_view = [
    Deny({"not": {"var": "current_user"}}),
    Allow({"==": [{"var": "current_user"}, {"var": "user"}]}),
    Allow({"var": "current_user.is_admin"}),
]


user_edit = [
    Deny({"not": {"var": "current_user"}}),
    Allow({"==": [{"var": "current_user"}, {"var": "user"}]}),
    Allow({"var": "current_user.is_admin"}),
]


book_view = [
    Allow({"var": "book.public"}),
    Deny({"not": {"var": "current_user"}}),
    Allow({"==": [{"var": "book.owner"}, {"var": "current_user.id"}]}),
    Allow({"var": "current_user.is_admin"}),
]


book_create = [
    Allow({"bool": {"var": "current_user"}}),
]


book_edit = [
    Deny({"not": {"var": "current_user"}}),
    Allow({"==": [{"var": "book.owner"}, {"var": "current_user.id"}]}),
    Allow({"var": "current_user.is_admin"}),
]


refs_edit = [  # References book.
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive.
    Allow({"var": "current_user.is_admin"}),
]


ref_add = [  # Reference item.
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive. Ownership of reference.
    Allow({"var": "current_user.is_admin"}),
]


ref_edit = [  # Reference item.
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive. Ownership of reference.
    Allow({"var": "current_user.is_admin"}),
]

imgs_edit = [  # Images book.
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive.
    Allow({"var": "current_user.is_admin"}),
]


img_view = [
    Allow({"var": "img.public"}),
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive. Ownership of image.
    Allow({"var": "current_user.is_admin"}),
]

img_add = [
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive. Ownership of image.
    Allow({"var": "current_user.is_admin"}),
]


img_edit = [
    Deny({"not": {"var": "current_user"}}),
    # XXX Should be less restrictive. Ownership of image.
    Allow({"var": "current_user.is_admin"}),
]
