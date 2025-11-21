"Markdown parser."

import html
import json
import re
import urllib.parse

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


# Globals; yes, awful coding, but it works...

# 1) Creating URL for indexed word requires knowing the book.
_current_book = None  # Required for index links.

# 2) URL for editing an item.
_current_edit_href = None


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


class Comment(marko.inline.InlineElement):
    "Markdown extension for comment."

    pattern = re.compile(r"\[!(.+?)\]")
    parse_children = False

    def __init__(self, match):
        self.comment = match.group(1).strip()


class CommentRenderer:
    "Output a the comment text."

    def render_comment(self, element):
        return f'<span class="comment">{element.comment}</span>'


class ThematicBreakRenderer:
    "Thematic break before a paragraph."

    def render_thematic_break(self, element):
        return '<hr class="break" />\n'


class Chunkmark(marko.inline.InlineElement):
    "Markdown extension for chunk number and edit button."

    pattern = re.compile(r"§(\d+)§")
    parse_children = False

    def __init__(self, match):
        self.nchunk = match.group(1)


class ChunkmarkRenderer:
    "Output the chunk number and edit button."

    def render_chunkmark(self, element):
        global _current_book
        global _current_edit_href
        if _current_book.chunk_numbers:
            result = [f'<mark id="{element.nchunk}">{element.nchunk}.</mark>']
        else:
            result = [f'<span id="{element.nchunk}"></span>']
        if _current_edit_href:
            result.append(
                f'<a href="{_current_edit_href}?nchunk={element.nchunk}" title="{Tx("Edit chunk")}"><img src="/edit.svg" class="white no-print"></a>'
            )
        return " ".join(result) + "\n"


def to_ast(content):
    "Convert Markdown content into an AST structure."
    converter = marko.Markdown(renderer=marko.ast_renderer.ASTRenderer)
    converter.use("footnote")
    converter.use(
        marko.helpers.MarkoExtension(
            elements=[Subscript, Superscript, Emdash, Indexed, Reference, Comment],
        )
    )
    return converter.convert(content)


class HtmlRenderer(marko.html_renderer.HTMLRenderer):
    "Modified HTML renderer for some elements."

    def render_fenced_code(self, element):
        if element.lang:
            lang = f' class="language-{self.escape_html(element.lang)}"'
        else:
            lang = ""
        return "<pre><code{}>{}</code></pre>\n".format(
            lang, html.escape(element.children[0].children)  # type: ignore
        )

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
        # Fetch image from the web.
        if urllib.parse.urlparse(element.dest).scheme:
            url = self.escape_url(element.dest)
            return f'<article><img src="{url}" {title} />{footer}</article>'
        try:
            img = get_imgs()[element.dest]
        except Error:
            return f"<article><b>Error</b>: no such image '{element.dest}'{footer}</article>"

        # Use the image from the image library.
        # SVG, use as such. 'title' is not used.
        if img["content_type"] == constants.SVG_MIMETYPE:
            return f'<article>{img["data"]}{footer}</article>'
        # Vega-Lite, convert to SVG. 'title' is not used.
        elif img["content_type"] == constants.JSON_MIMETYPE:
            svg = vl_convert.vegalite_to_svg(json.loads(img["data"]))
            return f"<article>{svg}{footer}</article>"
        # One of PNG or JPEG, use inline variant. Set title if not done.
        else:
            if not title:
                title = f' title="{self.escape_html(img.title)}"'
            src = f'data:{img["content_type"]};base64, {img["data"]}'
            return f'<article><img src="{src}" {title} />{footer}</article>'


class Markdown2Html(marko.Markdown):
    "Add new elements and extended HTML display features."

    def __init__(self):
        super().__init__(renderer=HtmlRenderer)
        self.use("footnote")
        self.use(
            marko.helpers.MarkoExtension(
                elements=[
                    Subscript,
                    Superscript,
                    Emdash,
                    Indexed,
                    Reference,
                    Comment,
                    Chunkmark,
                ],
                renderer_mixins=[
                    SubscriptRenderer,
                    SuperscriptRenderer,
                    EmdashRenderer,
                    IndexedRenderer,
                    ReferenceRenderer,
                    CommentRenderer,
                    ThematicBreakRenderer,
                    ChunkmarkRenderer,
                ],
            )
        )
        self._setup_extensions()

    def parse(self, text):
        chunked = Chunked(text)
        chunked.add_markdown()
        return super().parse(chunked.content)


def to_html(content, book=None, edit_href=None):
    global _current_book  # Required for index links.
    if book is not None:
        _current_book = book  # Required for index links generated in the next call.
    global _current_edit_href  # Required for editing chunk.
    _current_edit_href = edit_href
    return Markdown2Html().convert(content)


class Chunked:
    "Helper class for chunk processing."

    def __init__(self, content):
        self.chunks = constants.CHUNK_PATTERN.split(content)

    def add_markdown(self):
        nchunk = 0
        for pos, chunk in enumerate(self.chunks):
            if chunk.startswith("[^"):  # Footnote definition; do not allow chunk edit.
                pass
            elif chunk.startswith("---"):  # Thematic break; do not allow chunk edit.
                pass
            else:
                nchunk += 1
                self.chunks[pos] = f"§{nchunk}§\n" + chunk

    def get(self, nchunk):
        chunk_number = 0
        for chunk in self.chunks:
            if chunk.startswith("[^"):  # Footnote definition; do not allow chunk edit.
                pass
            elif chunk.startswith("---"):  # Thematic break; do not allow chunk edit.
                pass
            else:
                chunk_number += 1
                if nchunk == chunk_number:
                    return chunk

    def replace(self, content, nchunk):
        chunk_number = 0
        for pos, chunk in enumerate(self.chunks):
            if chunk.startswith("[^"):  # Footnote definition; do not allow chunk edit.
                pass
            elif chunk.startswith("---"):  # Thematic break; do not allow chunk edit.
                pass
            else:
                chunk_number += 1
                if nchunk == chunk_number:
                    self.chunks[pos] = content
                    break

    @property
    def content(self):
        return "\n\n".join(self.chunks)
