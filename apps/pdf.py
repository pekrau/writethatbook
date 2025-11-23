"Create PDF file of book or item using the ReportLab package."

import base64
import datetime
import io
import json
import urllib.parse

import reportlab
import reportlab.rl_config
import reportlab.lib.colors
from reportlab.lib.styles import *
from reportlab.platypus import *
from reportlab.platypus.doctemplate import LayoutError
from reportlab.platypus.tables import *
from reportlab.platypus.tableofcontents import TableOfContents, SimpleIndex

import PIL
import requests
import svglib.svglib
import vl_convert

from fasthtml.common import *

import auth
import books
from books import Book, get_imgs
import components
import constants
from errors import *
import minixml
import users
import utils
from utils import Tx


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book):
    "Get the parameters for downloading the book as PDF file."
    auth.authorize(request, *auth.book_view, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    title_page_metadata = bool(settings.get("title_page_metadata", False))
    output_comments = bool(settings.get("output_comments", False))
    include_status = settings.get("include_status", constants.CREATED)
    include_status_options = [
        Option(Tx(str(s)), value=repr(s), selected=include_status == s)
        for s in constants.STATUSES
        if s != constants.OMITTED
    ]
    page_break_level = int(settings.get("page_break_level", 1))
    page_break_options = []
    for value in range(0, constants.PDF_MAX_PAGE_BREAK_LEVEL + 1):
        if value == page_break_level:
            page_break_options.append(Option(str(value), selected=True))
        else:
            page_break_options.append(Option(str(value)))
    toc_level = int(settings.get("toc_level", 0))
    toc_level_options = []
    for value in range(0, constants.PDF_MAX_TOC_LEVEL + 1):
        if value == toc_level:
            toc_level_options.append(Option(str(value), selected=True))
        else:
            toc_level_options.append(Option(str(value)))

    footnotes_location = settings.get(
        "footnotes_location", constants.FOOTNOTES_EACH_TEXT
    )
    footnotes_options = []
    for value in constants.FOOTNOTES_LOCATIONS:
        if value == footnotes_location:
            footnotes_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            footnotes_options.append(Option(Tx(value.capitalize()), value=value))

    reference_font = settings.get("reference_font", constants.NORMAL)
    reference_font_options = []
    for value in constants.FONT_STYLES:
        if value == reference_font:
            reference_font_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            reference_font_options.append(Option(Tx(value.capitalize()), value=value))

    indexed_font = settings.get("indexed_font", constants.NORMAL)
    indexed_font_options = []
    for value in constants.FONT_STYLES:
        if value == indexed_font:
            indexed_font_options.append(
                Option(Tx(value.capitalize()), value=value, selected=True)
            )
        else:
            indexed_font_options.append(Option(Tx(value.capitalize()), value=value))

    fields = [
        Div(
            Fieldset(
                Label(
                    Input(
                        type="checkbox",
                        name="title_page_metadata",
                        role="switch",
                        checked=title_page_metadata,
                    ),
                    Tx("Metadata on title page"),
                ),
            ),
            Fieldset(
                Label(
                    Input(
                        type="checkbox",
                        name="output_comments",
                        role="switch",
                        checked=output_comments,
                    ),
                    Tx("Output comments"),
                ),
            ),
            cls="grid",
        ),
        Div(
            Fieldset(
                Label(Tx("Lowest status included")),
                Select(*include_status_options, name="include_status"),
            ),
            Fieldset(
                Label(Tx("Footnotes location")),
                Select(*footnotes_options, name="footnotes_location"),
            ),
            cls="grid",
        ),
        Div(
            Fieldset(
                Label(Tx("Page break level")),
                Select(*page_break_options, name="page_break_level"),
            ),
            Fieldset(
                Label(Tx("Table of contents level")),
                Select(*toc_level_options, name="toc_level"),
            ),
            cls="grid",
        ),
        Div(
            Fieldset(
                Label(Tx("Reference font")),
                Select(*reference_font_options, name="reference_font"),
            ),
            Fieldset(
                Label(Tx("Indexed font")),
                Select(*indexed_font_options, name="indexed_font"),
            ),
            cls="grid",
        ),
    ]

    title = Tx("Book as PDF file")
    return (
        Title(title),
        components.header(request, title, book=book),
        Main(
            Form(
                *fields,
                components.save_button(Tx("Book as PDF file")),
                action=f"/pdf/{book}",
                method="post",
            ),
            components.cancel_button(f"/book/{book}"),
            cls="container",
        ),
        components.footer(request, book),
    )


@rt("/{book:Book}")
def post(request, book: Book, form: dict):
    "Actually download the book as PDF file."
    auth.authorize(request, *auth.book_view, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["output_comments"] = bool(form.get("output_comments", False))
    settings["include_status"] = form.get("include_status", repr(constants.CREATED))
    settings["page_break_level"] = int(form.get("page_break_level", 1))
    settings["toc_level"] = int(form.get("toc_level", 0))
    settings["footnotes_location"] = form.get(
        "footnotes_location", constants.FOOTNOTES_EACH_TEXT
    )
    settings["reference_font"] = form.get("reference_font", constants.NORMAL)
    settings["indexed_font"] = form.get("indexed_font", constants.NORMAL)

    # Save settings.
    if auth.authorized(request, *auth.book_edit, book=book):
        book.write()

    return Response(
        content=BookWriter(book).get_content(),
        media_type=constants.PDF_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.pdf"'},
    )


@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str, position: int = None):
    "Download the item as a PDF file."
    auth.authorize(request, *auth.book_view, book=book)
    if not path:
        return components.redirect(f"/book/{book}")

    if not "pdf" in book.frontmatter:
        raise Error("no PDF output parameters have been set")

    item = book[path]
    return Response(
        content=ItemWriter(book).get_content(item),
        media_type=constants.PDF_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{item.title}.pdf"'},
    )


class Writer:
    "General PDF document writer."

    def __init__(self, book):
        self.book = book
        self.references = books.get_refs()

        # General settings.
        if book.frontmatter.get("chunk_numbers"):  # Display paragraph numbers.
            self.paragraph_number = 0
        else:
            self.paragraph_number = None

        # PDF-specific settings.
        settings = book.frontmatter.get("pdf", {})
        self.title_page_metadata = bool(settings.get("title_page_metadata", False))
        self.output_comments = bool(settings.get("output_comments", False))
        self.include_status = constants.Status.lookup(
            settings.get("include_status", constants.CREATED), constants.CREATED
        )
        self.page_break_level = int(settings.get("page_break_level", 1))
        self.toc_level = int(settings.get("toc_level", 0))
        self.footnotes_location = settings.get(
            "footnotes_location", constants.FOOTNOTES_EACH_TEXT
        )
        self.reference_font = settings.get("reference_font", constants.NORMAL)
        self.indexed_font = settings.get("indexed_font", constants.NORMAL)

        self.stylesheet = getSampleStyleSheet()
        # self.stylesheet.list()

        # These modifications will affect subsquent styles inheriting from Normal.
        self.stylesheet["Normal"].fontName = constants.PDF_NORMAL_FONT
        self.stylesheet["Normal"].fontSize = constants.PDF_NORMAL_FONT_SIZE
        self.stylesheet["Normal"].leading = constants.PDF_NORMAL_LEADING

        self.stylesheet["Title"].fontSize = constants.PDF_TITLE_FONT_SIZE
        self.stylesheet["Title"].leading = constants.PDF_TITLE_LEADING
        self.stylesheet["Title"].alignment = 0  # Left
        self.stylesheet["Title"].spaceAfter = constants.PDF_TITLE_SPACE_AFTER

        self.stylesheet["Code"].fontName = constants.PDF_CODE_FONT
        self.stylesheet["Code"].fontSize = constants.PDF_CODE_FONT_SIZE
        self.stylesheet["Code"].leading = constants.PDF_CODE_LEADING
        self.stylesheet["Code"].leftIndent = constants.PDF_CODE_INDENT

        self.stylesheet["OrderedList"].fontName = constants.PDF_NORMAL_FONT
        self.stylesheet["OrderedList"].fontSize = constants.PDF_NORMAL_FONT_SIZE
        self.stylesheet["OrderedList"].bulletFormat = "%s. "
        self.stylesheet["UnorderedList"].fontName = constants.PDF_NORMAL_FONT
        self.stylesheet["UnorderedList"].fontSize = constants.PDF_NORMAL_FONT_SIZE
        self.stylesheet["UnorderedList"].bulletType = "bullet"
        self.stylesheet["UnorderedList"].bulletFont = constants.PDF_NORMAL_FONT_SIZE

        self.stylesheet.add(
            ParagraphStyle(
                name="Index",
                parent=self.stylesheet["Normal"],
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Quote",
                parent=self.stylesheet["Normal"],
                fontName=constants.PDF_QUOTE_FONT,
                fontSize=constants.PDF_QUOTE_FONT_SIZE,
                leading=constants.PDF_QUOTE_LEADING,
                spaceBefore=constants.PDF_QUOTE_SPACE_BEFORE,
                leftIndent=constants.PDF_QUOTE_INDENT,
                rightIndent=constants.PDF_QUOTE_INDENT,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Synopsis",
                parent=self.stylesheet["Normal"],
                spaceAfter=constants.PDF_SYNOPSIS_SPACE_AFTER,
                leftIndent=constants.PDF_SYNOPSIS_INDENT,
                rightIndent=constants.PDF_SYNOPSIS_INDENT,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Footnote",
                parent=self.stylesheet["Normal"],
                leftIndent=constants.PDF_FOOTNOTE_INDENT,
                firstLineIndent=-constants.PDF_FOOTNOTE_INDENT,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Footnote subsequent",
                parent=self.stylesheet["Footnote"],
                firstLineIndent=0,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Reference",
                parent=self.stylesheet["Normal"],
                spaceBefore=constants.PDF_REFERENCE_SPACE_BEFORE,
                leftIndent=constants.PDF_REFERENCE_INDENT,
                firstLineIndent=-constants.PDF_REFERENCE_INDENT,
            )
        )

        # Placed here to avoid affecting previously defined styles.
        self.stylesheet["Normal"].spaceBefore = constants.PDF_NORMAL_SPACE_BEFORE
        self.stylesheet["Normal"].spaceAfter = constants.PDF_NORMAL_SPACE_AFTER

        # Key: fulltitle; value: dict(label, number, ast_children)
        self.footnotes = {}
        # References identifiers.
        self.referenced = set()

        self.current_text = None
        self.flowables = []
        self.list_stack = []
        self.index = SimpleIndex(style=self.stylesheet["Index"], headers=False)
        self.any_indexed = False

    def write_section(self, section, level):
        if section.status == constants.OMITTED:
            return
        if level <= self.page_break_level:
            self.add_pagebreak()
        self.add_heading(section.heading, level, section.ordinal)
        if section.subtitle:
            self.add_heading(section.subtitle, level + 1)
        if section.synopsis:
            self.add_paragraph("<i>" + section.synopsis + "</i>", "Synopsis")

        self.current_text = section
        self.render(section.ast)

        if self.footnotes_location == constants.FOOTNOTES_EACH_TEXT:
            self.write_text_footnotes(section)

        for item in section.items:
            if item.is_section:
                self.write_section(item, level=level + 1)
            else:
                self.write_text(item, level=level + 1)

    def write_text(self, text, level):
        if text.status == constants.OMITTED:
            return
        if level <= self.page_break_level:
            self.add_pagebreak()
        if not text.frontmatter.get("suppress_title"):
            self.add_heading(text.heading, level, text.ordinal)
            if text.subtitle:
                self.add_heading(text.subtitle, level + 1)
        if text.synopsis:
            self.add_paragraph("<i>" + text.synopsis + "</i>", "Synopsis")

        self.current_text = text
        self.render(text.ast)

        if self.footnotes_location == constants.FOOTNOTES_EACH_TEXT:
            self.write_text_footnotes(text)

    def write_text_footnotes(self, text):
        "Footnote definitions at the end of each text."
        assert self.footnotes_location == constants.FOOTNOTES_EACH_TEXT
        try:
            footnotes = self.footnotes[text.fulltitle]
        except KeyError:
            return
        self.add_heading(Tx("Footnotes"), constants.MAX_LEVEL)
        for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
            self.within_footnote = f"<b>{entry['number']}.</b> "
            for child in entry["ast_children"]:
                self.render(child)
            self.within_footnote = False

    def write_chapter_footnotes(self, item):
        "Footnote definitions at the end of a chapter; i.e. top-level section."
        assert self.footnotes_location == constants.FOOTNOTES_EACH_CHAPTER
        try:
            footnotes = self.footnotes[item.chapter.fulltitle]
        except KeyError:
            return
        self.add_pagebreak()
        self.add_heading(Tx("Footnotes"), int(constants.MAX_LEVEL / 2))
        for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
            self.within_footnote = f"<b>{entry['number']}.</b> "
            for child in entry["ast_children"]:
                self.render(child)
            self.within_footnote = False

    def write_book_footnotes(self):
        "Footnote definitions as a separate section at the end of the book."
        assert self.footnotes_location == constants.FOOTNOTES_END_OF_BOOK
        self.add_pagebreak()
        self.add_heading(Tx("Footnotes"), 1, anchor="footnotes")
        for item in self.book.items:
            footnotes = self.footnotes.get(item.fulltitle, {})
            if not footnotes:
                continue
            self.add_heading(item.heading, 2)
            for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
                self.within_footnote = f"<b>{entry['number']}.</b> "
                for child in entry["ast_children"]:
                    self.render(child)
                self.within_footnote = False

    def write_references(self):
        "Write the references pages."
        assert self.referenced
        self.add_pagebreak()
        self.add_heading(Tx("References"), 1, anchor="references")
        for refid in sorted(self.referenced):
            self.para_push("Reference")
            try:
                reference = self.references[refid]
            except Error:
                continue
            self.para_text(f'<a name="{reference["id"]}"/><b>{reference["name"]}</b>')
            self.para_text('<span size="40"> </span>')
            self.write_reference_authors(reference)
            try:
                method = getattr(self, f"write_reference_{reference['type']}")
            except AttributeError:
                print("unknown", reference["type"])
            else:
                method(reference)
            self.write_reference_external_links(reference)
            self.para_pop()

    def write_reference_authors(self, reference):
        count = len(reference["authors"])
        for pos, author in enumerate(reference["authors"]):
            if pos > 0:
                if pos == count - 1:
                    self.para_text(" & ")
                else:
                    self.para_text(", ")
            self.para_text(utils.short_person_name(author))

    def write_reference_article(self, reference):
        "Write data for reference of type 'article'."
        self.para_text(f' ({reference["year"]})')
        self.para_text(f" {reference.reftitle}")
        journal = reference.get("journal")
        if journal:
            self.para_text(f" <i>{journal}</i>")
        try:
            self.para_text(f" {reference['volume']}")
        except KeyError:
            pass
        else:
            try:
                self.para_text(f" ({reference['number']})")
            except KeyError:
                pass
        try:
            self.para_text(f": pp. {reference['pages'].replace('--', '-')}.")
        except KeyError:
            pass

    def write_reference_book(self, reference):
        "Write data for reference of type 'book'."
        self.para_text(f' ({reference["year"]}).')
        self.para_text(f" <i>{reference.reftitle}</i>")
        try:
            self.para_text(f" {reference['publisher']}")
        except KeyError:
            pass
        try:
            self.para_text(f", {reference['edition_published']}")
        except KeyError:
            pass

    def write_reference_link(self, reference):
        "Write data for reference of type 'link'."
        self.para_text(f' ({reference["year"]})')
        self.para_text(f" {reference.reftitle}")
        try:
            self.para_text(
                f' <link href="{reference["url"]}" underline="true" color="blue">{reference["url"]}</link>'
            )
        except KeyError:
            pass
        else:
            try:
                self.para_text(f" (accessed {reference['accessed']})")
            except KeyError:
                pass

    def write_reference_external_links(self, reference):
        "Write external links; doi, pmid, isbn, ..."
        links = []
        for key, (label, template) in constants.REFS_LINKS.items():
            try:
                value = reference[key]
                text = f"{label}:{value}"
                url = template.format(value=value)
                links.append((text, url))
            except KeyError:
                pass
        if not links:
            return
        for pos, (text, url) in enumerate(links):
            if pos == 0:
                self.para_text(" ")
            else:
                self.para_text(", ")
            self.para_text(
                f'<link href="{url}" underline="true" color="blue">{text}</link>'
            )

    def write_indexed(self):
        "Write the index."
        assert self.any_indexed
        self.add_pagebreak()
        self.add_heading(Tx("Index"), 1, anchor="index")
        self.flowables.append(self.index)

    def render(self, ast):
        "Render the content AST node hierarchy."
        try:
            method = getattr(self, f"render_{ast['element']}")
        except AttributeError:
            print("Could not handle ast", ast)
        else:
            method(ast)

    def render_document(self, ast):
        self.within_quote = False
        self.within_code = False
        self.within_footnote = False
        self.para_stack = []
        for child in ast["children"]:
            self.render(child)

    def render_heading(self, ast):
        self.para_push(f"Heading{ast['level']}")
        for child in ast["children"]:
            self.render(child)
        level = min(ast["level"], constants.MAX_LEVEL)
        self.para_pop()

    def render_paragraph(self, ast):
        self.para_push()
        if self.paragraph_number is not None and not self.within_footnote:
            self.paragraph_number += 1
            self.para_text('<font face="courier">')
            self.para_text(f"{self.paragraph_number}.")
            self.para_text("</font> ")
        for child in ast["children"]:
            self.render(child)
        stylename = None
        preformatted = None
        if self.within_quote:
            stylename = "Quote"
        elif self.within_code:
            stylename = "Code"
            preformatted = True
        elif self.within_footnote:
            if isinstance(self.within_footnote, str):
                self.para_stack[-1][0].insert(0, self.within_footnote)
                self.within_footnote = True
                stylename = "Footnote"
            else:
                stylename = "Footnote subsequent"
        self.para_pop(stylename=stylename, preformatted=preformatted)

    def render_raw_text(self, ast):
        self.para_text(ast["children"])

    def render_blank_line(self, ast):
        pass

    def render_quote(self, ast):
        self.para_push("Quote")
        self.within_quote = True
        for child in ast["children"]:
            self.render(child)
        self.within_quote = False
        self.para_pop()

    def render_code_span(self, ast):
        self.para_text(f'<font face="{constants.PDF_QUOTE_FONT}">')
        self.para_text(ast["children"])
        self.para_text("</font>")

    def render_code_block(self, ast):
        self.para_push("Code", preformatted=True)
        self.within_code = True
        for child in ast["children"]:
            self.render(child)
        self.within_code = False
        self.para_pop()

    def render_fenced_code(self, ast):
        self.para_push("Code", preformatted=True)
        self.within_code = True
        for child in ast["children"]:
            self.render(child)
        self.within_code = False
        self.para_pop()

    def render_image(self, ast):
        self.para_pop()
        self.para_push()
        flowables = [
            HRFlowable(
                width="100%",
                color=reportlab.lib.colors.grey,
                spaceBefore=4,
                spaceAfter=constants.PDF_IMAGE_SPACE,
            )
        ]
        # Fetch image from the web.
        if urllib.parse.urlparse(ast["dest"]).scheme:
            response = requests.get(ast["dest"])
            if response.status_code != HTTP.OK:
                flowables.append(Paragraph(f"Could not fetch image '{ast['dest']}'"))
            elif response.headers["Content-Type"] in (
                constants.PNG_MIMETYPE,
                constants.JPEG_MIMETYPE,
            ):
                image_data = io.BytesIO(response.content)
                flowables.append(Image(image_data, hAlign="LEFT"))
            else:
                flowables.append(
                    Paragraph(
                        f"Cannot handle image '{ast['dest']}' with content type '{response.headers['Content-Type']}'"
                    )
                )

        # Use image from the image library.
        elif ast["dest"] in get_imgs():
            img = get_imgs()[ast["dest"]]
            scale_factor = img["pdf"]["scale_factor"]

            if img["content_type"] in (
                constants.SVG_MIMETYPE,
                constants.JSON_MIMETYPE,
            ):
                # SVG image.
                if img["content_type"] == constants.SVG_MIMETYPE:
                    # SVG in image library has already been checked for validity.
                    root = minixml.parse_content(img["data"])

                # Vega-Lite plot.
                else:
                    # JSON in image library has already been checked for validity.
                    vl_spec = json.loads(img["data"])
                    root = minixml.parse_content(vl_convert.vegalite_to_svg(vl_spec))

                # Set viewbox so that scaling behaves.
                root["viewBox"] = f"0 0 {root['width']} {root['height']}"

                # SVG convert to ReportLab graphics.
                if img["pdf"]["reportlab_graphics"]:
                    # Scale width and height in SVG element.
                    root["width"] = scale_factor * float(root["width"])
                    root["height"] = scale_factor * float(root["height"])
                    flowables.append(svglib.svglib.svg2rlg(io.StringIO(repr(root))))

                # SVG convert to PNG.
                else:
                    png_factor = img["pdf"]["png_rendering_factor"]
                    # Scale width and height in SVG element.
                    root["width"] = png_factor * scale_factor * float(root["width"])
                    root["height"] = png_factor * scale_factor * float(root["height"])
                    flowables.append(
                        Image(
                            io.BytesIO(vl_convert.svg_to_png(repr(root))),
                            hAlign="LEFT",
                            width=float(root["width"]) / png_factor,
                            height=float(root["height"]) / png_factor,
                        )
                    )

            # JPEG or PNG.
            elif img["content_type"] in (
                constants.PNG_MIMETYPE,
                constants.JPEG_MIMETYPE,
            ):
                image_data = io.BytesIO(base64.standard_b64decode(img["data"]))
                width, height = PIL.Image.open(image_data).size
                flowables.append(
                    Image(
                        image_data,
                        hAlign="LEFT",
                        width=scale_factor * width,
                        height=scale_factor * height,
                    )
                )
            else:
                flowables.append(
                    Paragraph(
                        f"Cannot handle image content type '{img['content_type']}'"
                    )
                )
        else:
            flowables.append(Paragraph(f"No such image '{ast['dest']}'"))

        if ast["children"]:
            self.para_push("Normal")
            for child in ast["children"]:
                self.render(child)
            flowables.append(self.para_pop(add=False))
        flowables.append(
            HRFlowable(
                width="100%",
                color=reportlab.lib.colors.grey,
                spaceBefore=4,
                spaceAfter=constants.PDF_IMAGE_SPACE,
            )
        )
        self.flowables.append(KeepTogether(flowables))

    def render_emphasis(self, ast):
        self.para_text("<i>")
        for child in ast["children"]:
            self.render(child)
        self.para_text("</i>")

    def render_strong_emphasis(self, ast):
        self.para_text("<b>")
        for child in ast["children"]:
            self.render(child)
        self.para_text("</b>")

    def render_superscript(self, ast):
        self.para_text("<super>")
        for child in ast["children"]:
            self.render(child)
        self.para_text("</super>")

    def render_subscript(self, ast):
        self.para_text("<sub>")
        for child in ast["children"]:
            self.render(child)
        self.para_text("</sub>")

    def render_emdash(self, ast):
        self.para_text(constants.EM_DASH)

    def render_line_break(self, ast):
        # XXX Cannot handle hard/soft distinction.
        self.para_text(" ")

    def render_thematic_break(self, ast):
        self.flowables.append(
            HRFlowable(width="60%", color=reportlab.lib.colors.black, spaceAfter=10)
        )

    def render_link(self, ast):
        self.para_text(f'<link href="{ast["dest"]}" underline="true" color="blue">')
        for child in ast["children"]:
            self.render(child)
        self.para_text("</link>")

    def render_list(self, ast):
        self.list_stack.append([])
        for child in ast["children"]:
            self.render(child)
        # XXX ast["tight"] is currently not used.
        if ast["ordered"]:
            style = self.stylesheet["OrderedList"]
        else:
            style = self.stylesheet["UnorderedList"]
        flowable = ListFlowable(self.list_stack.pop(), style=style)
        if self.list_stack:
            self.list_stack[-1].append(flowable)
        else:
            self.flowables.append(flowable)

    def render_list_item(self, ast):
        self.list_stack.append([])
        for child in ast["children"]:
            self.render(child)
        item = ListItem(self.list_stack.pop())
        self.list_stack[-1].append(item)

    def render_indexed(self, ast):
        if self.indexed_font == constants.ITALIC:
            fs = "<i>"
            fe = "</i>"
        elif self.indexed_font == constants.BOLD:
            fs = "<b>"
            fe = "</b>"
        elif self.indexed_font == constants.UNDERLINE:
            fs = "<u>"
            fe = "</u>"
        else:
            fs = ""
            fe = ""
        item = ast["canonical"].replace(",", ",,").replace(";", ",")
        self.para_text(f'<index item="{item}"/>')
        self.para_text(f'{fs}{ast["term"]}{fe}')
        self.any_indexed = True

    def render_footnote_ref(self, ast):
        # The label is used only for lookup; a number is shown in the output.
        label = ast["label"]
        if self.footnotes_location == constants.FOOTNOTES_EACH_TEXT:
            entries = self.footnotes.setdefault(self.current_text.fulltitle, {})
            number = len(entries) + 1
            key = label
        elif self.footnotes_location in (
            constants.FOOTNOTES_EACH_CHAPTER,
            constants.FOOTNOTES_END_OF_BOOK,
        ):
            fulltitle = self.current_text.chapter.fulltitle
            entries = self.footnotes.setdefault(fulltitle, {})
            number = len(entries) + 1
            key = f"{fulltitle}-{label}"
        entries[key] = dict(label=label, number=number)
        self.para_text(f"<super><b>{number}</b></super>")

    def render_footnote_def(self, ast):
        "Add footnote definition to lookup."
        label = ast["label"]
        if self.footnotes_location == constants.FOOTNOTES_EACH_TEXT:
            fulltitle = self.current_text.fulltitle
            key = label
        elif self.footnotes_location in (
            constants.FOOTNOTES_EACH_CHAPTER,
            constants.FOOTNOTES_END_OF_BOOK,
        ):
            fulltitle = self.current_text.chapter.fulltitle
            key = f"{fulltitle}-{label}"
        # Footnote def may be missing.
        try:
            self.footnotes[fulltitle][key]["ast_children"] = ast["children"]
        except KeyError:
            pass

    def render_reference(self, ast):
        if ast["id"] in self.references:
            self.referenced.add(ast["id"])
            if self.reference_font == constants.ITALIC:
                fs = "<i>"
                fe = "</i>"
            elif self.reference_font == constants.BOLD:
                fs = "<b>"
                fe = "</b>"
            elif self.reference_font == constants.UNDERLINE:
                fs = "<u>"
                fe = "</u>"
            else:
                fs = ""
                fe = ""
            self.para_text(f'<link href="#{ast["id"]}">{fs}{ast["name"]}{fe}</link>')
        else:
            self.para_text(f'??? no such refid {ast["id"]} ???')

    def render_comment(self, ast):
        if self.output_comments:
            self.para_text(f'<span backcolor="yellow"><b>{ast["comment"]}</b></span>')

    def add_paragraph(self, text, stylename="Normal"):
        self.flowables.append(Paragraph(text, style=self.stylesheet[stylename]))

    def add_preformatted(self, text, stylename="Normal"):
        self.flowables.append(Preformatted(text, style=self.stylesheet[stylename]))

    def add_heading(self, heading, level, anchor=None):
        """Add heading given the level.
        If the anchor is given, create TOC entry and anchor.
        """
        level = min(level, constants.MAX_LEVEL)
        if anchor:
            if level <= self.toc_level:
                self.flowables.append(TocMarker(level - 1, heading, anchor))
            heading = f'<a name="__anchor__{anchor}"/>' + heading
        self.add_paragraph(heading, stylename=f"Heading{level}")

    def add_pagebreak(self):
        self.flowables.append(NotAtTopPageBreak())

    def para_push(self, stylename="Normal", preformatted=False):
        "Push new container for text in a paragraph onto the stack."
        self.para_stack.append(([], stylename, preformatted))

    def para_pop(self, stylename=None, preformatted=None, add=True):
        "Output paragraph containing the saved-up text."
        popped = self.para_stack.pop()
        parts = popped[0]
        if stylename is None:
            stylename = popped[1]
        if preformatted is None:
            preformatted = popped[2]
        text = "".join(parts)
        if self.list_stack:
            if preformatted:
                self.list_stack[-1].append(
                    Preformatted(text, style=self.stylesheet[stylename])
                )
            else:
                self.list_stack[-1].append(
                    Paragraph(text, style=self.stylesheet[stylename])
                )
        elif add:
            if preformatted:
                self.add_preformatted(text, stylename)
            else:
                self.add_paragraph(text, stylename)
        else:
            return Paragraph(text, style=self.stylesheet[stylename])

    def para_text(self, text):
        "Add text to container on top of stack."
        self.para_stack[-1][0].append(text)

    def display_page_number(self, canvas, doc):
        "Output page number onto the current canvas."
        width, height = reportlab.rl_config.defaultPageSize
        canvas.saveState()
        canvas.setFont("Helvetica", 10)
        canvas.drawString(width - 84, height - 56, str(doc.page))
        canvas.restoreState()


class TocDocTemplate(SimpleDocTemplate):
    "Subclass for creating a table of contents."

    def __init__(self, filename, toc_level, **kw):
        super().__init__(filename, **kw)
        self.toc_level = toc_level

    def afterFlowable(self, flowable):
        if not isinstance(flowable, TocMarker):
            return
        if self.toc_level < flowable.toc_level:
            return
        key = f"__{flowable.toc_anchor}__"
        self.canv.bookmarkPage(key)
        self.notify("TOCEntry", (flowable.toc_level, flowable.toc_text, self.page, key))


class TocMarker(NullDraw):
    "Marker for TOC entry."

    def __init__(self, toc_level, toc_text, toc_anchor):
        super().__init__()
        self.toc_level = toc_level
        self.toc_text = toc_text
        self.toc_anchor = toc_anchor


class BookWriter(Writer):
    "PDF book writer."

    def get_content(self):
        "Create the PDF document of the book return its content."
        # Write book title page containing authors and metadata.
        self.add_paragraph(self.book.title, "Title")
        self.flowables.append(
            HRFlowable(width="100%", color=reportlab.lib.colors.black, spaceAfter=20)
        )
        if self.book.subtitle:
            self.add_paragraph(self.book.subtitle, "Heading1")
        for author in self.book.authors:
            self.add_paragraph(", ".join(self.book.authors), "Heading2")
        self.flowables.append(Spacer(0, 28))

        self.render(self.book.ast)

        if self.title_page_metadata:
            self.flowables.append(Spacer(0, 100))
            self.add_preformatted(
                f'{Tx("Status")}: {Tx(self.book.status)}\n'
                f'{Tx("Created")}: {utils.str_datetime_display()}\n'
                f'{Tx("Modified")}: {utils.str_datetime_display(self.book.modified)}',
                stylename="Italic",
            )

        # Write table of contents (TOC) page(s).
        if self.toc_level and self.book.items:
            self.add_pagebreak()
            self.add_paragraph(Tx("Contents"), "Heading1")
            level_styles = []
            for level in range(0, constants.PDF_MAX_TOC_LEVEL + 1):
                style = ParagraphStyle(
                    name=f"TOC level {level}",
                    fontName=constants.PDF_NORMAL_FONT,
                    fontSize=constants.PDF_TOC_FONT_SIZE,
                    leading=constants.PDF_TOC_LEADING,
                    firstLineIndent=constants.PDF_TOC_INDENT * level,
                    leftIndent=constants.PDF_TOC_INDENT * (level + 1),
                )
                level_styles.append(style)
            self.toc = TableOfContents(
                dotsMinLevel=-1,
                levelStyles=level_styles,
                notifyKind="TOCEntry",
            )
            self.flowables.append(self.toc)

        # First-level items are chapters.
        for item in self.book.items:
            if item.status == constants.OMITTED:
                continue
            if item.status < self.include_status:
                continue

            if item.is_section:
                self.write_section(item, level=1)
            else:
                self.write_text(item, level=1)

            if self.footnotes_location == constants.FOOTNOTES_EACH_CHAPTER:
                self.write_chapter_footnotes(item)

        if self.footnotes_location == constants.FOOTNOTES_END_OF_BOOK:
            self.write_book_footnotes()

        if self.referenced:
            self.write_references()

        output = io.BytesIO()
        if self.toc_level:
            document = TocDocTemplate(
                output,
                toc_level=self.toc_level,
                title=self.book.title,
                author=", ".join(self.book.authors) or None,
                creator=f"writethatbook {constants.__version__}",
                lang=self.book.language,
            )

            if self.any_indexed:
                self.write_indexed()
                document.multiBuild(
                    self.flowables,
                    onLaterPages=self.display_page_number,
                    canvasmaker=self.index.getCanvasMaker(),
                )
            else:
                document.multiBuild(
                    self.flowables, onLaterPages=self.display_page_number
                )
        else:
            document = SimpleDocTemplate(
                output,
                title=self.book.title,
                author=", ".join(self.book.authors) or None,
                creator=f"writethatbook {constants.__version__}",
                lang=self.book.language,
            )
            if self.any_indexed:
                document.build(
                    self.flowables,
                    onLaterPages=self.display_page_number,
                    canvasmaker=self.index.getCanvasMaker(),
                )
            else:
                document.build(self.flowables, onLaterPages=self.display_page_number)
        return output.getvalue()


class ItemWriter(Writer):
    "PDF item (section or text) writer."

    def get_content(self, item):
        "Create the PDF document of the given item and return its content."
        # Force footnotes at end of each text.
        self.footnotes_location = constants.FOOTNOTES_EACH_TEXT

        self.skip_first_add_page = False
        if item.is_section:
            self.write_section(item, level=item.level)
        else:
            self.write_text(item, level=item.level)

        if self.referenced:
            self.write_references()
        if self.any_indexed:
            self.write_indexed()

        output = io.BytesIO()
        document = SimpleDocTemplate(
            output,
            title=item.title,
            author=", ".join(self.book.authors) or None,
            creator=f"writethatbook {constants.__version__}",
            lang=self.book.language,
        )
        try:
            if self.any_indexed:
                document.build(
                    self.flowables,
                    onFirstPage=self.display_page_number,
                    onLaterPages=self.display_page_number,
                    canvasmaker=self.index.getCanvasMaker(),
                )
            else:
                document.build(
                    self.flowables,
                    onFirstPage=self.display_page_number,
                    onLaterPages=self.display_page_number,
                )
        except LayoutError as error:
            raise Error(str(error))
        return output.getvalue()
