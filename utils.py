"Various simple utility functions."

import csv
import datetime
import hashlib
from http import HTTPStatus as HTTP
import io
import json
import os
from pathlib import Path
import re
import string
import tarfile
import time
import unicodedata

import requests

import constants
import latex_utf8


class Error(Exception):
    "Custom exception; return response with message and status code."

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def short_name(name):
    "Return the person name in short form; given names as initials."
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 1:
        return name
    initials = [p.strip()[0] for p in parts.pop().split(" ")]
    parts.append("".join([f"{i}." for i in initials]))
    return ", ".join(parts)


def full_title(reference):
    "Return the full title for the reference."
    title = reference.get("title")
    if not title:
        title = "[no title]"
    if reference.get("subtitle"):
        title += ": " + reference["subtitle"]
    return title.rstrip(".") + "."


def thousands(i):
    return f"{i:,}".replace(",", ".")


def cleanup_latex(value):
    "Convert LaTeX characters to UTF-8, remove newlines and normalize blanks."
    return latex_utf8.from_latex_to_utf8(" ".join(value.split()))


def cleanup_whitespaces(value):
    "Replace all whitespaces with blanks."
    return " ".join([s for s in value.split()])


SAFE_CHARACTERS = set(string.ascii_letters + string.digits)


def nameify(title):
    "Make name (lowercase letters, digits, ASCII-only) out of a title."
    result = unicodedata.normalize("NFKD", title).encode("ASCII", "ignore")
    return "".join(
        [c.lower() if c in SAFE_CHARACTERS else "-" for c in result.decode("utf-8")]
    )


VALID_ID_RX = re.compile(r"[a-z][a-z0-9_]*")


def valid_id(id):
    "Check that the identifier is valid."
    return bool(VALID_ID_RX.match(id))


def get_digest(c):
    "Return the digest instance having processed frontmatter and content."
    result = hashlib.md5()
    frontmatter = c.frontmatter.copy()
    frontmatter.pop("digest", None)  # Necessary!
    result.update(json.dumps(frontmatter, sort_keys=True).encode("utf-8"))
    result.update(c.content.encode("utf-8"))
    return result


def timestr(filepath=None, localtime=True, display=True, safe=False):
    "Return time string for modification date of the given file, or now."
    if filepath:
        timestamp = os.path.getmtime(filepath)
        if localtime:
            result = datetime.datetime.fromtimestamp(timestamp)
        else:
            result = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
    elif localtime:
        result = datetime.datetime.now()
    else:
        result = datetime.datetime.now(datetime.UTC)
    result = result.strftime(constants.DATETIME_ISO_FORMAT)
    if not display:
        result = result.replace(" ", "T") + "Z"
    if safe:
        result = result.replace(" ", "_").replace(":", "-")
    return result


def wildcard_to_regexp(pattern):
    """Convert a shell-like wildcard pattern into a proper regexp pattern.
    Very basic implementation!
    """
    pattern = pattern.replace("*", ".*")
    pattern = pattern.replace("?", ".?")
    return pattern


def tolocaltime(utctime):
    "Convert a time string in UTC to local time."
    mytz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    lt = datetime.datetime.fromisoformat(utctime).astimezone(mytz)
    return lt.strftime(constants.DATETIME_ISO_FORMAT)


def get_state_remote(bid=None):
    "Get the remote site state, optionally for the given bid."
    if "MDBOOK_UPDATE_SITE" not in os.environ:
        raise Error(
            "remote update site undefined; missing MDBOOK_UPDATE_SITE",
            HTTP.INTERNAL_SERVER_ERROR,
        )
    if "MDBOOK_UPDATE_APIKEY" not in os.environ:
        raise Error(
            "remote update apikey undefined; missing MDBOOK_UPDATE_APIKEY",
            HTTP.INTERNAL_SERVER_ERROR,
        )
    url = os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + "/state"
    if bid:
        url += "/" + bid
    headers = dict(apikey=os.environ["MDBOOK_UPDATE_APIKEY"])
    response = requests.get(url, headers=headers)
    if response.status_code == 404 or not response.content:
        return {}
    elif response.status_code != 200:
        raise Error(
            f"remote {url} response error: {response.status_code}; {response.content}",
            HTTP.INTERNAL_SERVER_ERROR,
        )
    return response.json()


def get_tgzfile(dirpath):
    """Return an io.BytesIO object containing the gzipped tar file
    contents of the given directory.
    """
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as tgzfile:
        for path in dirpath.iterdir():
            tgzfile.add(path, arcname=path.name, recursive=True)
    return result


def unpack_tgzfile(dirpath, content, references=False):
    "Unpack the contents of a TGZ file into the given directory."
    if not content:
        raise Error("empty TGZ file", HTTP.BAD_REQUEST)
    try:
        tf = tarfile.open(fileobj=io.BytesIO(content), mode="r:gz")
        if "index.md" not in tf.getnames():
            raise Error(
                "no 'index.md' file in TGZ file; not from mdbook?", HTTP.BAD_REQUEST
            )
        if references:
            # No subdirectories or non-Markdown files are allowed in references.
            for name in tf.getnames():
                if not name.endswith(".md"):
                    raise Error(
                        "reference TGZ file must contain only *.md files",
                        HTTP.BAD_REQUEST,
                    )
                if Path(name).name != name:
                    raise Error(
                        "reference TGZ file must contain no directories",
                        HTTP.BAD_REQUEST,
                    )
            filter = lambda tf, path: tf if tf.name != "index.md" else None
        else:
            filter = None
        tf.extractall(path=dirpath, filter=filter)
    except tarfile.TarError as message:
        raise Error(f"tar file error: {message}", HTTP.BAD_REQUEST)


class Translator:
    "Simple translation of words and phrases from one language to another."

    def __init__(self, translation_csv_file, source=None, target=None):
        """The CSV file must have one column per language.
        The header of each column specifies the name of the language.
        """
        with open(translation_csv_file) as infile:
            self.terms = list(csv.DictReader(infile))
        self.source = source or tuple(self.terms[0].keys())[0]
        self.target = target or tuple(self.terms[0].keys())[1]
        self.set_translation(self.source, self.target)

    def __str__(self):
        return f"{self.__class__.__name__} {self.source} -> {self.target}"

    @property
    def languages(self):
        return tuple(self.terms[0].keys())

    def set_translation(self, source, target):
        if source not in self.terms[0]:
            raise ValueError(f"language 'source' not in the translation data.")
        if target not in self.terms[0]:
            raise ValueError(f"language 'target' not in the translation data.")
        self.translation = {}
        for term in self.terms:
            self.translation[term[source]] = term[target]
            self.translation[term[source].lower()] = term[target].lower()
            self.translation[term[source].upper()] = term[target].upper()
            self.translation[term[source].capitalize()] = term[target].capitalize()

    def __call__(self, term):
        return self.translation.get(str(term), term).rstrip("*")


Tx = Translator(constants.TRANSLATIONS_FILEPATH)


class Timer:
    "Timer for process CPU time."

    def __init__(self):
        self.restart()

    def __str__(self):
        return f"{self.elapsed:.3f}"

    @property
    def elapsed(self):
        return time.process_time() - self.start

    def restart(self):
        self.start = time.process_time()


if __name__ == "__main__":
    for id in ["id", "i", "å", "2an", "z9123_", "z_123", "a___"]:
        print(id, valid_id(id))
