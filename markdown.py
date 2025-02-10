"Markdown parser."

import json
import re

import marko
import marko.ast_renderer
import marko.inline
import marko.helpers

import vl_convert as vlc
import yaml

import constants
import utils
from utils import Tx


# Terrible kludge: creating URL for indexed word requires knowing
# the book, so this global variable keeps track of it.

_current_book = None  # Required for index links.


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

    pattern = re.compile(r"(\s\-\-\s)")
    parse_children = False


class EmdashRenderer:
    "Output em-dash character."

    def render_emdash(self, element):
        return " " + constants.EM_DASH + " "


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


class FencedCodeRenderer:
    "Handle fenced code for SVG code and Vega-Lite specification."

    def render_fenced_code(self, element):
        content = element.children[0].children

        # SVG content must contain the root 'svg' element with 'xmlns'.
        if element.lang == "svg":
            return f"<article>\n{content}\n</article>\n"

        # Output Vega-Lite specification as SVG.
        elif element.lang == "vega-lite":
            try:
                spec = json.loads(content)
            except json.JSONDecodeError as error:
                return f"<article>Error parsing JSON: {error}</article>"
            try:
                svg = vlc.vegalite_to_svg(spec)
            except ValueError as error:
                return f"<article>Error converting to SVG: {error}</article>"
            try:
                description = spec["description"]
            except KeyError:
                return f"<article>\n{svg}\n</article>\n"
            else:
                description = html_converter.convert(description)
                return f"<article>\n{svg}\n<footer>{description}</footer></article>\n"

        # All other fenced code.
        else:
            return super().render_fenced_code(element)


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
            FencedCodeRenderer,
        ],
    )
)


ast_converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
ast_converter.use("footnote")
ast_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Indexed, Reference],
    )
)

to_ast = ast_converter.convert


POSITION = "!!position!!"
NEW_PARAGRAPH_RX = re.compile(r"\n\n")
EDIT_BUTTON_RX = re.compile(r"!!([^ ]+) ([0-9]+) ([0-9]+)!!")


def to_html(book, content, position=None, edit_href=None):
    global _current_book  # Required for index links.
    # Insert the position marker before converting to HTML, to get the position right.
    if position is not None:  # Note: extra newline needed for fenced block!
        content = content[:position] + POSITION + "\n" + content[position:]
    if edit_href:
        content = AddEditButtons(content, edit_href).processed
    _current_book = book  # Required for index links generated in the next call.
    html = html_converter.convert(content)
    # Replace the position marker with a proper invisible HTML construct.
    html = html.replace(POSITION, '<span id="position"></span>')
    # Replace the edit button markers with proper HTML links.
    if edit_href:
        html = EDIT_BUTTON_RX.sub(get_edit_button, html)
    return html


def get_edit_button(match):
    return f' <a href="{match.group(1)}?first={match.group(2)}&last={match.group(3)}" title="{Tx("Edit paragraph")}"><img src="/edit.svg" class="white"></a>'


class AddEditButtons:
    "Add edit button marker to each paragraph."

    def __init__(self, content, edit_href):
        self.edit_href = edit_href
        self.content = content + "\n\n"  # Handle last paragraph.
        self.offset = 0
        # Handle the offset produced by the POSITION marker.
        try:
            self.position = self.content.index(POSITION)
        except ValueError:
            self.position = None
        self.first = 0
        self.processed = NEW_PARAGRAPH_RX.sub(self, self.content)

    def __call__(self, match):
        self.last = match.start()
        result = self.get_marker(self.first, self.last)
        self.first = match.end()
        if self.first > 4 and self.content[self.first - 5 : self.first] == "```\n\n":
            return "\n" + result
        else:
            return result

    def get_marker(self, first, last):
        # Handle the offset produced by the POSITION marker.
        if self.position is not None and first > self.position:
            offset = len(POSITION) + 1  # Deal with that extra newline.
            first -= offset
            last -= offset
        return f"\n!!{self.edit_href} {first} {last}!!\n\n"
