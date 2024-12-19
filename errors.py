"Exceptions and their handlers."

from http import HTTPStatus as HTTP
import urllib

from fasthtml.common import Response, RedirectResponse

__all__ = [
    "Error",
    "error_handler",
    "NotAllowed",
    "not_allowed_handler"
]


class Error(Exception):
    "Custom exception; return response with message and status code."

    def __init__(self, message, status_code=HTTP.BAD_REQUEST):
        super().__init__(message)
        self.status_code = status_code


def error_handler(request, exc):
    "Return a response with the message and status code."
    return Response(content=str(exc), status_code=exc.status_code)


class NotAllowed(Exception):
    "Not allowed to access a page."
    pass


def not_allowed_handler(request, exc):
    """If logged in, then forbidden since authorization failed.
    If not logged in, then redirect to login.
    """
    if request.scope.get("current_user"):
        return Response(content="Forbidden", status_code=HTTP.FORBIDDEN)
    else:
        path = urllib.parse.urlencode({"path": request.url.path})
        return RedirectResponse(f"/user/login?{path}", status_code=HTTP.SEE_OTHER)
