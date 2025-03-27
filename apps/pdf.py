"Create PDF file of book or item using the ReportLab package."

import datetime
import io
import json
import xml.etree.ElementTree

import reportlab
import reportlab.rl_config
import reportlab.lib.colors
from reportlab.lib.styles import *
from reportlab.platypus import *
from reportlab.platypus.tables import *
from reportlab.platypus.tableofcontents import TableOfContents, SimpleIndex

import PIL
import vl_convert

from fasthtml.common import *

import auth
import books
from books import Book
import components
import constants
from errors import *
import markdown
import users
import utils
from utils import Tx


PAGE_WIDTH, PAGE_HEIGHT = reportlab.rl_config.defaultPageSize
BLACK = reportlab.lib.colors.black


app, rt = components.get_fast_app()


@rt("/{book:Book}")
def get(request, book: Book):
    "Get the parameters for downloading the book as PDF file."
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    title_page_metadata = bool(settings.get("title_page_metadata", False))
    page_break_level = int(settings.get("page_break_level", 1))
    page_break_options = []
    for value in range(0, constants.PDF_MAX_PAGE_BREAK_LEVEL + 1):
        if value == page_break_level:
            page_break_options.append(Option(str(value), selected=True))
        else:
            page_break_options.append(Option(str(value)))
    toc_pages = bool(settings.get("toc_pages"))
    toc_level = settings.get("toc_level", 1)
    toc_level_options = []
    for value in range(1, constants.PDF_MAX_TOC_LEVEL + 1):
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
        Fieldset(
            Legend(Tx("Metadata on title page")),
            Label(
                Input(
                    type="checkbox",
                    name="title_page_metadata",
                    role="switch",
                    checked=title_page_metadata,
                ),
                Tx("Display"),
            ),
        ),
        Fieldset(
            Legend(Tx("Page break level")),
            Select(*page_break_options, name="page_break_level"),
        ),
        Fieldset(
            Legend(Tx("Table of contents pages")),
            Label(
                Input(
                    type="checkbox",
                    name="toc_pages",
                    role="switch",
                    checked=toc_pages,
                ),
                Tx("Display"),
            ),
        ),
        Fieldset(
            Legend(Tx("Table of contents level")),
            Select(*toc_level_options, name="toc_level"),
        ),
        Fieldset(
            Legend(Tx("Footnotes location")),
            Select(*footnotes_options, name="footnotes_location"),
        ),
        Fieldset(
            Legend(Tx("Reference font")),
            Select(*reference_font_options, name="reference_font"),
        ),
        Fieldset(
            Legend(Tx("Indexed font")),
            Select(*indexed_font_options, name="indexed_font"),
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
    auth.authorize(request, *auth.book_view_rules, book=book)

    settings = book.frontmatter.setdefault("pdf", {})
    settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
    settings["page_break_level"] = int(form["page_break_level"])
    settings["toc_pages"] = bool(form.get("toc_pages"))
    settings["toc_level"] = int(form["toc_level"])
    settings["footnotes_location"] = form["footnotes_location"]
    settings["reference_font"] = form["reference_font"]
    settings["indexed_font"] = form["indexed_font"]

    # Save settings.
    if auth.authorized(request, *auth.book_edit_rules, book=book):
        book.write()

    return Response(
        content=BookWriter(book).get_content(),
        media_type=constants.PDF_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{book.title}.pdf"'},
    )

@rt("/{book:Book}/{path:path}")
def get(request, book: Book, path: str, position: int = None):
    "Download the item as a PDF file."
    auth.authorize(request, *auth.book_view_rules, book=book)
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

        settings = book.frontmatter["pdf"]
        self.title_page_metadata = bool(settings["title_page_metadata"])
        self.page_break_level = int(settings["page_break_level"])
        self.toc_pages = bool(settings["toc_pages"])
        self.toc_level = int(settings["toc_level"])
        self.footnotes_location = settings["footnotes_location"]
        self.reference_font = settings.get("reference_font")
        self.indexed_font = settings.get("indexed_font")

        self.stylesheet = getSampleStyleSheet()
        self.stylesheet["Title"].fontSize = 24
        self.stylesheet["Title"].leading = 30
        self.stylesheet["Title"].alignment = 0
        self.stylesheet["Title"].spaceAfter = 15
        self.stylesheet["Code"].fontSize = 9
        self.stylesheet["Code"].leading = 10
        self.stylesheet["Code"].leftIndent = 28
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
                fontName="Times-Roman",
                fontSize=11,
                leading=14,
                spaceBefore=6,
                leftIndent=28,
                rightIndent=28,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="List",
                parent=self.stylesheet["Normal"],
                spaceBefore=14,
                spaceAfter=14,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="List tight",
                parent=self.stylesheet["Normal"],
                spaceBefore=4,
                spaceAfter=4,
            )
        )
        self.stylesheet.add(
            ParagraphStyle(
                name="Footnote",
                parent=self.stylesheet["Normal"],
                spaceBefore=4,
                firstLineIndent=-10,
                leftIndent=10,
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
                spaceAfter=5,
                firstLineIndent=-20,
                leftIndent=20,
            )
        )
        self.stylesheet["Normal"].leading = 15
        self.stylesheet["Normal"].spaceBefore = 5
        self.stylesheet["Normal"].spaceAfter = 5

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
            self.within_footnote = None

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
            self.within_footnote = None

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
                self.within_footnote = None

    def write_references(self):
        "Write the references pages."
        assert self.referenced
        self.add_pagebreak()
        self.add_heading(Tx("References"), 1, anchor="references")
        for refid in sorted(self.referenced):
            self.para_push()
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
            self.para_pop("Reference")

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
        self.para_text("<br/>")
        for pos, (text, url) in enumerate(links):
            if pos != 0:
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
        self.para_push()
        for child in ast["children"]:
            self.render(child)
        level = min(ast["level"], constants.MAX_LEVEL)
        self.para_pop(f"Heading{level}")

    def render_paragraph(self, ast):
        self.para_push()
        stylename = "Normal"
        preformatted = False
        for child in ast["children"]:
            self.render(child)
        if self.within_quote:
            stylename = "Quote"
        elif self.within_code:
            stylename = "Code"
            preformatted = True
        elif self.within_footnote:
            if isinstance(self.within_footnote, str):
                self.para_stack[-1].insert(0, self.within_footnote)
                self.within_footnote = True
                stylename = "Footnote"
            else:
                stylename = "Footnote subsequent"
        self.para_pop(stylename, preformatted=preformatted)

    def render_raw_text(self, ast):
        self.para_text(ast["children"])

    def render_blank_line(self, ast):
        pass

    def render_quote(self, ast):
        self.within_quote = True
        self.para_push()
        for child in ast["children"]:
            self.render(child)
        self.para_pop("Quote")
        self.within_quote = False

    def render_code_span(self, ast):
        self.para_text('<font face="courier">')
        self.para_text(ast["children"])
        self.para_text("</font>")

    def render_code_block(self, ast):
        self.within_code = True
        self.para_push()
        for child in ast["children"]:
            self.render(child)
        self.para_pop("Code", preformatted=True)
        self.within_code = False

    def render_fenced_code(self, ast):
        "Fenced code may be SVG or Vega-Lite."
        content = ast["children"][0]["children"]
        # scale = 0.75  # Empirical scale factor...

        # # Output SVG as PNG.
        # if ast.get("lang") == "svg":
        #     root = xml.etree.ElementTree.fromstring(content)
        #     # SVG content must contain the root 'svg' element with xmlns.
        #     # Add it if missing.
        #     if root.tag == "svg":
        #         content = content.replace("<svg", f'<svg xmlns="{constants.XMLNS_SVG}"')
        #         root = xml.etree.ElementTree.fromstring(content)
        #     png = io.BytesIO(vl_convert.svg_to_png(content))
        #     im = PIL.Image.open(png)
        #     width, height = im.size
        #     self.pdf.image(im, w=scale * width, h=scale * height)
        #     desc = root.find(f"./{{{constants.XMLNS_SVG}}}desc")
        #     if desc is not None:
        #         self.state.set(
        #             family=constants.CAPTION_FONT,
        #             font_size=constants.CAPTION_FONT_SIZE,
        #             left_indent=constants.CAPTION_LEFT_INDENT,
        #         )
        #         self.render(markdown.to_ast(desc.text))
        #         self.state.reset()

        # # Output Vega-Lite specification as PNG.
        # elif ast.get("lang") == "vega-lite":
        #     vl_spec = json.loads(content)
        #     png = io.BytesIO(vl_convert.vegalite_to_png(vl_spec))
        #     im = PIL.Image.open(png)
        #     width, height = im.size
        #     self.pdf.image(im, w=scale * width, h=scale * height)
        #     description = vl_spec.get("description")
        #     if description:
        #         dast = markdown.to_ast(description)
        #         self.state.set(
        #             family=constants.CAPTION_FONT,
        #             font_size=constants.CAPTION_FONT_SIZE,
        #             left_indent=constants.CAPTION_LEFT_INDENT,
        #         )
        #         self.render(dast)
        #         self.state.reset()

        # # Fenced code as is.
        # else:
        #     self.state.set(
        #         family=constants.CODE_FONT,
        #         left_indent=constants.CODE_LEFT_INDENT,
        #         line_height=1.2,
        #     )
        #     for child in ast["children"]:
        #         self.render(child)
        #     self.state.reset()
        # self.state.ln()

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
        self.flowables.append(HRFlowable(width="60%", color=BLACK, spaceAfter=10))

    def render_link(self, ast):
        self.para_text(f'<link href="{ast["dest"]}" underline="true" color="blue">')
        for child in ast["children"]:
            self.render(child)
        self.para_text("</link>")

    def render_list(self, ast):
        self.list_stack.append([])
        for child in ast["children"]:
            self.render(child)
        if ast["tight"]:
            style = self.stylesheet["List tight"]
        else:
            style = self.stylesheet["List"]
        if ast["ordered"]:
            bullet_type = "1"
            bullet_format = "%s."
        else:
            bullet_type = "bullet"
            bullet_format = None
        flowable = ListFlowable(
            self.list_stack.pop(),
            bulletFontSize=style.bulletFontSize,
            bulletType=bullet_type,
            bulletFormat=bullet_format,
            spaceBefore=style.spaceBefore,
            spaceAfter=style.spaceAfter,
        )
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

    def para_push(self):
        "Push new container for text in a paragraph onto the stack."
        self.para_stack.append([])

    def para_pop(self, stylename, preformatted=False):
        "Output paragraph containing the saved-up text."
        text = "".join(self.para_stack[-1])
        if self.list_stack:
            if preformatted:
                self.list_stack[-1].append(
                    Preformatted(text, style=self.stylesheet[stylename])
                )
            else:
                self.list_stack[-1].append(
                    Paragraph(text, style=self.stylesheet[stylename])
                )
        else:
            if preformatted:
                self.add_preformatted(text, stylename)
            else:
                self.add_paragraph(text, stylename)

    def para_text(self, text):
        "Add text to container on top of stack."
        self.para_stack[-1].append(text)

    def display_page_number(self, canvas, doc):
        "Output page number onto the current canvas."
        canvas.saveState()
        canvas.setFont("Helvetica", 10)
        canvas.drawString(PAGE_WIDTH - 84, PAGE_HEIGHT - 56, str(doc.page))
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
        if self.toc_pages and self.book.items:
            self.add_pagebreak()
            self.add_paragraph(Tx("Contents"), "Heading1")
            level_styles = []
            for level in range(0, constants.PDF_MAX_TOC_LEVEL + 1):
                style = ParagraphStyle(
                    name=f"TOC level {level}",
                    fontName="Helvetica",
                    fontSize=10,
                    leading=11,
                    firstLineIndent=15 * level,
                    leftIndent=15 + 15 * level,
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
        if self.toc_pages:
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
                document.multiBuild(self.flowables, onLaterPages=self.display_page_number)
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
        return output.getvalue()
