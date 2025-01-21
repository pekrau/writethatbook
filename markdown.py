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


# Terrible kludge: creating URL for indexed word requires knowing
# the book, so this global variable keeps track of it.

_current_book = None        # Required for index links.


def get_index_href(canonical):
    global _current_book
    return f"/meta/index/{_current_book}#{canonical}"


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
        return f'<a class="contrast" title="{title}" href="{get_index_href(element.canonical)}">{element.term}</a>'


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


class ThematicBreakRenderer:
    "Thematic break before a paragraph."

    def render_thematic_break(self, element):
        return '<hr class="break" />\n'



html_converter = marko.Markdown()
html_converter.use("footnote")
html_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Indexed, Reference],
        renderer_mixins=[
            SubscriptRenderer,
            SuperscriptRenderer,
            EmdashRenderer,
            IndexedRenderer,
            ReferenceRenderer,
            ThematicBreakRenderer,
        ],
    )
)


class AddEditButtons:
    "Add edit button to each paragraph."

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
            return f'!!{self.href} {first} {last}!!\n\n'
        else:  # No change.
            return "\n\n"


EDITBUTTON_RX = re.compile(r"!!([^ ]+) ([0-9]+) ([0-9]+)!!")


def to_html(book, content, prev_edit=None, edit_href=None):
    global _current_book        # Required for index links.
    # Insert the prev-edit marker before converting to HTML, to get the position right.
    marker = "!!prev-edit!!"
    if prev_edit is not None:
        content = content[:prev_edit] + marker + content[prev_edit:]
    if edit_href:
        content = AddEditButtons(content, href=edit_href).processed
    _current_book = book        # Required for index links.
    html = html_converter.convert(content)
    # Replace the prev-edit marker with a proper invisible HTML construct.
    html = html.replace(marker, '<span id="prev-edit"></span>')
    if edit_href:
        html = EDITBUTTON_RX.sub(edit_button, html)
    return html

def edit_button(match):
    return f'<a href="{match.group(1)}?first={match.group(2)}&last={match.group(3)}" title="{Tx("Edit paragraph")}"><img src="/edit.svg" class="white"></a>'


ast_converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
ast_converter.use("footnote")
ast_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Indexed, Reference],
    )
)

to_ast = ast_converter.convert
