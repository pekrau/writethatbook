"Various simple utility functions."

import csv
import datetime
import hashlib
import os
import re
import string
import time
import unicodedata

import babel.dates
import babel.numbers

import constants


def get_digest_instance(content, digest=None):
    "Return a new digest instance, or update it, with the given string content."
    assert isinstance(content, str)
    if digest is None:
        digest = hashlib.md5()
    digest.update(content.encode("utf-8"))
    return digest


def get_digest(content, digest=None):
    """Return the hex digest code for the content.
    The given digest instance, if any, is updated by the content.
    """
    return get_digest_instance(content, digest=digest).hexdigest()


def short_person_name(name):
    "Return the person name in short form; given names as initials."
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 1:
        return name
    initials = [p.strip()[0] for p in parts.pop().split(" ")]
    parts.append("".join([f"{i}." for i in initials]))
    return ", ".join(parts)


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


def str_datetime_iso(dt):
    "Return the datetime instance as ISO format string."
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def str_datetime_safe(dt=None):
    """Return the datetime as ISO format string with safe characters.
    If no datetime instance, then use now in UTC.
    """
    if dt is None:
        dt = datetime.datetime.now(tz=datetime.UTC)
    return (
        dt.isoformat(timespec="seconds")
        .replace("+00:00", "Z")
        .replace(":", "_")
        .replace(" ", "_")
    )


def str_datetime_display(dt=None):
    """Return the UTC datetime instance formatted for the locale.
    If no datetime instance, then use now in UTC.
    """
    if dt is None:
        dt = datetime.datetime.now(tz=datetime.UTC)
    return babel.dates.format_datetime(
        dt,
        tzinfo=constants.DEFAULT_TIMEZONE,
        locale=constants.DEFAULT_LOCALE,
        format="short",
    )


def thousands(i):
    "Return integer as string formatted according to locale."
    return babel.numbers.format_decimal(i, locale=constants.DEFAULT_LOCALE)


def wildcard_to_regexp(pattern):
    """Convert a shell-like wildcard pattern into a proper regexp pattern.
    Very basic implementation!
    """
    pattern = pattern.replace("*", ".*")
    pattern = pattern.replace("?", ".?")
    return pattern


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
        return self.translation.get(str(term), str(term)).rstrip("*")


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
