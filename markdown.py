"Markdown parser."

import json
import re

import marko
import marko.html_renderer
import marko.ast_renderer
import marko.inline
import marko.helpers

import vl_convert

import constants
from errors import *
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

    pattern = re.compile(r"(\-\-)(?=\s)")
    parse_children = False


class EmdashRenderer:
    "Output em-dash character."

    def render_emdash(self, element):
        return constants.EM_DASH


class Indexed(marko.inline.InlineElement):
    "Markdown extension for indexed term."

    pattern = re.compile(r"\[#(.+?)(\|(.+?))?\]", re.S)  # Yes, this isn't quite right.
    parse_children = False

    def __init__(self, match):
        self.term = match.group(1).strip()
        if match.group(3):  # Because of the not-quite-right regexp...
            self.canonical = " ".join(match.group(3).strip().split())
        else:
            self.canonical = " ".join(self.term.split())


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
        return f'<strong><a href="/refs/view/{element.id}">{element.name}</a></strong>'


class ThematicBreakRenderer:
    "Thematic break before a paragraph."

    def render_thematic_break(self, element):
        return '<hr class="break" />\n'


class Editbutton(marko.inline.InlineElement):
    "Markdown extension for paragraph edit button marker."

    pattern = re.compile(r"!!!([^ ]+) ([0-9]+) ([0-9]+)!!!")
    parse_children = False

    def __init__(self, match):
        self.href = match.group(1)
        self.first = match.group(2)
        self.last = match.group(3)


class EditbuttonRenderer:
    "Output paragraph edit button."

    def render_editbutton(self, element):
        return f' <a href="{element.href}?first={element.first}&last={element.last}" title="{Tx("Edit paragraph")}"><img src="/edit.svg" class="white"></a>'


def to_ast(content):
    "Convert Markdown content into an AST structure."
    converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
    converter.use("footnote")
    converter.use(
        marko.helpers.MarkoExtension(
            elements=[Subscript, Superscript, Emdash, Indexed, Reference],
        )
    )
    return converter.convert(content)


POSITION = "!!POSITION!!"
CODE_BLOCK_PREFIX = "    "


class Position(marko.inline.InlineElement):
    "Markdown extension for edit position marker."

    pattern = re.compile(f"({POSITION})")
    parse_children = False


class PositionRenderer:
    "Output position marker."

    def render_position(self, element):
        return '<span id="position"></span>'


NEW_PARAGRAPH_RX = re.compile(r"\n\n")


class HtmlRenderer(marko.html_renderer.HTMLRenderer):
    "Modify behaviour of HTML renderer for some elements."

    def render_list(self, element):
        "Modified unordered list bullet display. XXX Doesn't work on Chrome?"
        if element.ordered:
            tag = "ol"
            extra = f' start="{element.start}"' if element.start != 1 else ""
        else:
            tag = "ul"
            if element.bullet == "-":
                extra = ' style="list-style-type: disc;"'
            elif element.bullet == "*":
                extra = ' style="list-style-type: square;"'
            elif element.bullet == "+":
                extra = ' style="list-style-type: circle;"'
            else:
                extra = ""
        return "<{tag}{extra}>\n{children}</{tag}>\n".format(
            tag=tag, extra=extra, children=self.render_children(element)
        )

    def render_image(self, element):
        """Modified to produce a footer caption from alt text.
        Fetch image from the image library, if available.
        """
        from books import get_imgs  # To avoid circular import.

        title = f' title="{self.escape_html(element.title)}"' if element.title else ""
        body = self.render_children(element)
        if body:
            footer = f"<footer>{body}</footer>"
        else:
            footer = ""
        try:
            img = get_imgs()[element.dest]
        except Error:
            # Fetch image from the web.
            url = self.escape_url(element.dest)
            return f'<article><img src="{url}" {title} />{footer}</article>'

        # Use the image from the image library.
        # SVG, use as such. 'title' is not used.
        if img["content_type"] == constants.SVG_CONTENT_TYPE:
            return f'<article>{img["data"]}{footer}</article>'
        # Vega-Lite, convert to SVG. 'title' is not used.
        elif img["content_type"] == constants.JSON_CONTENT_TYPE:
            svg = vl_convert.vegalite_to_svg(json.loads(img["data"]))
            return f"<article>{svg}{footer}</article>"
        # One of PNG or JPEG, use inline variant. Set title if not done.
        else:
            if not title:
                title = f' title="{self.escape_html(img.title)}"'
            src = f'data:{img["content_type"]};base64, {img["data"]}'
            return f'<article><img src="{src}" {title} />{footer}</article>'


def to_html(content, book=None, position=None, edit_href=None):
    global _current_book  # Required for index links.
    # Create new converter instance.
    converter = marko.Markdown(renderer=HtmlRenderer)
    converter.use("footnote")
    converter.use(
        marko.helpers.MarkoExtension(
            elements=[
                Subscript,
                Superscript,
                Emdash,
                Indexed,
                Reference,
                Editbutton,
                Position,
            ],
            renderer_mixins=[
                SubscriptRenderer,
                SuperscriptRenderer,
                EmdashRenderer,
                IndexedRenderer,
                ReferenceRenderer,
                ThematicBreakRenderer,
                EditbuttonRenderer,
                PositionRenderer,
            ],
        )
    )
    # Insert the position marker, if any.
    if position is not None:
        # Handle code block special case.
        if content[position:].startswith(CODE_BLOCK_PREFIX):
            content = content[:position] + POSITION + "\n\n" + content[position:]
        else:
            # Add newline to handle beginning of block.
            content = content[:position] + POSITION + "\n" + content[position:]
    # Insert the edit button markers, if any.
    if edit_href:
        content = AddEditbuttons(content, edit_href).processed
    if book is not None:
        _current_book = book  # Required for index links generated in the next call.
    return converter.convert(content)


class AddEditbuttons:
    "Add edit button marker to the end of each paragraph."

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
        self.processed = NEW_PARAGRAPH_RX.sub(self.add_marker, self.content)

    def add_marker(self, match):
        self.last = match.start()
        result = self.get_marker(self.first, self.last)
        self.first = match.end()
        return "\n" + result

    def get_marker(self, first, last):
        # Handle the offset produced by the POSITION marker.
        if self.position is not None:
            offset = len(POSITION)
            offset += 1  # Add one for newline for fenced block.
            if first > self.position:
                first -= offset
            if last > self.position:
                last -= offset
        if last < 0:
            return ""
        else:
            return f"!!!{self.edit_href} {first} {last}!!!\n\n"
