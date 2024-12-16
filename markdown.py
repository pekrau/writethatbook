"Markdown parser."

import re

import marko
import marko.ast_renderer
import marko.inline
import marko.helpers
import marko.ext.gfm

import yaml

import constants
import utils


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
        return (
            f'<a class="secondary" href="/index#{element.canonical}">{element.term}</a>'
        )


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
        return f'<strong><a href="/reference/{element.id}">{element.name}</a></strong>'


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
        ],
    )
)

convert_to_html = html_converter.convert


ast_converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
ast_converter.use("footnote")
ast_converter.use(
    marko.helpers.MarkoExtension(
        elements=[Subscript, Superscript, Emdash, Indexed, Reference],
    )
)

convert_to_ast = ast_converter.convert
