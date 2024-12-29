"Markdown parser."

import re

import marko
import marko.ast_renderer
import marko.inline
import marko.helpers

import yaml

import constants
import utils
from utils import Tx


class Subscript(marko.inline.InlineElement):
    "Markdown extension for subscript."

    pattern = re.compile(r"(?<!~)(~)([^~]+)\1(?!~)")
    priority = 5
    parse_children = True
    parse_group = 2


class SubscriptRenderer:
    "Output subscript text."

    def render_subscript(self, element):
        return f"<sub>{self.render_children(element)}</sub>"


class Superscript(marko.inline.InlineElement):
    "Markdown extension for superscript."

    pattern = re.compile(r"(?<!\^)(\^)([^\^]+)\1(?!\^)")
    priority = 5
    parse_children = True
    parse_group = 2


class SuperscriptRenderer:
    "Output superscript text."

    def render_superscript(self, element):
        return f"<sup>{self.render_children(element)}</sup>"


class Emdash(marko.inline.InlineElement):
    "Markdown extension for em-dash."

    pattern = re.compile(r"(?<!-)(--)(?!-)")
    parse_children = False


class EmdashRenderer:
    "Output em-dash character."

    def render_emdash(self, element):
        return constants.EM_DASH


class Lastedit(marko.inline.InlineElement):
    "Markdown extension for the position of the last edit in the text."

    pattern = re.compile("(LASTEDIT)")
    parse_children = False


class LasteditRenderer:
    "Output position of last edit in the text."

    def render_lastedit(self, element):
        return '<span id="lastedit"></span>'


class Indexed(marko.inline.InlineElement):
    "Markdown extension for indexed term."

    pattern = re.compile(r"\[#(.+?)(\|(.+?))?\]")  # I know, this isn't quite right.
    parse_children = False

    def __init__(self, match):
        self.term = match.group(1).strip()
        if match.group(3):  # Because of the not-quite-right regexp...
            self.canonical = match.group(3).strip()
        else:
            self.canonical = self.term


class IndexedRenderer:
    "Output a link to the index page and item."

    def render_indexed(self, element):
        if element.term == element.canonical:
            title = utils.Tx("Indexed")
        else:
            title = utils.Tx("Indexed") + ": " + element.canonical
        return f'<a class="contrast" title="{title}" href="/index#{element.canonical}">{element.term}</a>'


class Reference(marko.inline.InlineElement):
    "Markdown extension for reference."

    pattern = re.compile(r"\[@(.+?)\]")
    parse_children = False

    def __init__(self, match):
        self.name = match.group(1).strip()
        self.id = utils.nameify(self.name)


class ReferenceRenderer:
    "Output a link to the reference page and item."

    def render_reference(self, element):
        return f'<strong><a href="/refs/{element.id}">{element.name}</a></strong>'


html_converter = marko.Markdown()
html_converter.use("footnote")
html_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Lastedit, Indexed, Reference],
        renderer_mixins=[
            SubscriptRenderer,
            SuperscriptRenderer,
            EmdashRenderer,
            LasteditRenderer,
            IndexedRenderer,
            ReferenceRenderer,
        ],
    )
)


class Fragmenter:
    "Fragment content into paragraphs with separate edit buttons."

    PATTERN = re.compile(r"\n\n")

    def __init__(self, content, href=None):
        self.href = href
        self.content = content
        self.current = 0
        self.ranges = []
        self.processed = self.PATTERN.subn(self, content)[0]
        if self.ranges:
            self.ranges.append((self.ranges[-1][1] + 1, len(content)))
            self.processed += self.get_href(self.ranges[-1][0] + 1, self.ranges[-1][1])
        else:
            self.ranges.append((0, len(content)))
            self.processed += self.get_href(self.ranges[-1][0], self.ranges[-1][1])
        self.fragments = [self.content[s:e] for s, e in self.ranges]

    def __call__(self, match):
        start = match.start()
        self.ranges.append((self.current, start))
        result = self.get_href(self.current, start)
        self.current = match.end()
        return result

    def get_href(self, first, last):
        if self.href:
            return f' <a href="{self.href}?first={first}&last={last}" title="{Tx("Edit paragraph")}"><img src="/edit.svg"></a>\n\n'
        else:  # No change.
            return "\n\n"


def convert_to_html(content, href=None):
    if href:
        content = Fragmenter(content, href=href).processed
    return html_converter.convert(content)


ast_converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
ast_converter.use("footnote")
ast_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Lastedit, Indexed, Reference],
    )
)

convert_to_ast = ast_converter.convert
