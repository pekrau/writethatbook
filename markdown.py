"Markdown parser."

import json
import re

import marko
import marko.html_renderer
import marko.ast_renderer
import marko.inline
import marko.helpers

import vl_convert
import yaml

import constants
import minixml
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


class FencedCodeRenderer:
    "Handle fenced code for SVG code and Vega-Lite specification."

    def render_fenced_code(self, element):
        content = element.children[0].children

        # Output SVG after a few checks.
        if element.lang in ("svg", "svg-png"):
            return self.write_svg(content, element)

        # Output Vega-Lite specification as SVG.
        elif element.lang in ("vega-lite", "vega-lite-png"):
            try:
                spec = json.loads(content)
            except json.JSONDecodeError as error:
                return f"<article>Error parsing JSON: {error}</article>"
            try:
                svg = vl_convert.vegalite_to_svg(spec)
            except ValueError as error:
                return f"<article>Error converting to SVG: {error}</article>"
            return self.write_svg(svg, element)

        # All other fenced code.
        else:
            return super().render_fenced_code(element)

    def write_svg(self, content, element):
        "Output SVG after a few checks."
        # SVG content must contain the root 'svg' element with xmlns.
        try:
            root = minixml.parse_content(content)
            if root.tag != "svg":
                raise ValueError("XML root element must be 'svg'.")
            for key in ["width", "height"]:
                if key not in root:
                    raise ValueError(
                        f"XML 'svg' element must contain attribute '{key}'."
                    )
                try:
                    value = float(root[key])
                    if value <= 0:
                        raise ValueError
                except ValueError:
                    raise ValueError(
                        f"XML 'svg' attribute '{key}' must be positive number."
                    )
            # Root 'svg' element must contain xmlns; add if missing.
            if "xmlns" not in root:
                root["xmlns"] = constants.SVG_XMLNS
            desc = list(root.walk(lambda e: e.tag == "desc" and e.depth == 1))
            if desc:
                desc = desc[0].text
            else:
                desc = element.extra
            if desc:
                return f"<article>\n{content}\n<footer>{to_html(desc)}</footer>\n</article>\n"
            else:
                return f"<article>\n{content}\n</article>\n"
        except ValueError as error:
            return f"<article>Error handling SVG: {error}</article>"


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
    "Modify unordered list bullet display. XXX Doesn't work on Chrome?"

    def render_list(self, element):
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
                FencedCodeRenderer,
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
