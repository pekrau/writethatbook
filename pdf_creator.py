"Create PDF file."

import datetime
import io

import fpdf  # fpdf2, actually!

import utils
import constants
from utils import Tx, Error


class Creator:
    "PDF creator."

    def __init__(self, book, references):
        self.book = book
        self.references = references
        self.title = book.title
        self.subtitle = book.subtitle
        self.authors = book.authors
        self.language = book.language
        settings = book.frontmatter["pdf"]
        self.title_page_metadata = settings["title_page_metadata"]
        self.contents_pages = settings["contents_pages"]
        self.contents_level = int(settings["contents_level"])
        self.page_break_level = int(settings["page_break_level"])
        self.footnotes_location = settings["footnotes_location"]
        self.indexed_xref = settings["indexed_xref"]

    def create(self):
        "Create the PDF document; return a BytesIO instance containing it."
        if self.contents_pages:
            for contents_pages in range(1, 20):
                try:
                    return self.create_attempt(contents_pages)
                except fpdf.errors.FPDFException:
                    pass
        # If 20 isn't enough, give up and skip the contents page.
        return self.create_attempt(0)

    def create_attempt(self, contents_pages):
        "Attempt at writing PDF given the number of content pages to use."
        self.list_stack = []
        # Key: fulltitle; value: dict(label, number, ast_children)
        self.footnotes = {}
        # References, key: refid; value: reference
        self.referenced = set()
        # Key: canonical; value: dict(ordinal, fulltitle, heading, page)
        self.indexed = {}
        self.indexed_count = 0

        self.pdf = fpdf.FPDF(format="a4", unit="pt")
        self.pdf.set_title(self.title)
        if self.language:
            self.pdf.set_lang(self.language)
        if self.authors:
            self.pdf.set_author(", ".join(self.authors))
        self.pdf.set_creator(f"mdbook {constants.__version__}")
        self.pdf.set_creation_date(datetime.datetime.now())

        self.pdf.add_font(
            "FreeSans",
            style="",
            fname=constants.FONT_DIRPATH / "FreeSans.ttf",
        )
        self.pdf.add_font(
            "FreeSans",
            style="B",
            fname=constants.FONT_DIRPATH / "FreeSansBold.ttf",
        )
        self.pdf.add_font(
            "FreeSans",
            style="I",
            fname=constants.FONT_DIRPATH / "FreeSansOblique.ttf",
        )
        self.pdf.add_font(
            "FreeSans",
            style="BI",
            fname=constants.FONT_DIRPATH / "FreeSansBoldOblique.ttf",
        )
        self.pdf.add_font(
            "FreeSerif",
            style="",
            fname=constants.FONT_DIRPATH / "FreeSerif.ttf",
        )
        self.pdf.add_font(
            "FreeSerif",
            style="B",
            fname=constants.FONT_DIRPATH / "FreeSerifBold.ttf",
        )
        self.pdf.add_font(
            "FreeSerif",
            style="I",
            fname=constants.FONT_DIRPATH / "FreeSerifItalic.ttf",
        )
        self.pdf.add_font(
            "FreeSerif",
            style="BI",
            fname=constants.FONT_DIRPATH / "FreeSerifBoldItalic.ttf",
        )
        self.pdf.add_font(
            "FreeMono",
            style="",
            fname=constants.FONT_DIRPATH / "FreeMono.ttf",
        )
        self.pdf.add_font(
            "FreeMono",
            style="B",
            fname=constants.FONT_DIRPATH / "FreeMonoBold.ttf",
        )
        self.pdf.add_font(
            "FreeMono",
            style="I",
            fname=constants.FONT_DIRPATH / "FreeMonoOblique.ttf",
        )
        self.pdf.add_font(
            "FreeMono",
            style="BI",
            fname=constants.FONT_DIRPATH / "FreeMonoBoldOblique.ttf",
        )

        self.state = State(self.pdf)

        self.write_title_page()
        if contents_pages:
            self.pdf.add_page()
            self.pdf.start_section(Tx("Contents"), level=0)
            self.pdf.insert_toc_placeholder(self.write_toc, pages=contents_pages)
            self.skip_first_add_page = True
        else:
            self.skip_first_add_page = False

        self.current_text = None
        # First-level items are chapters.
        for item in self.book.items:
            if item.is_section:
                self.write_section(item, level=1)
            else:
                self.write_text(item, level=1)
            self.write_footnotes_chapter(item)
        self.write_footnotes_book()
        self.write_references()
        self.write_indexed()

        # This may fail if the number of content pages is wrong.
        output = io.BytesIO()
        self.pdf.output(output)
        return output

    def write_title_page(self):
        self.pdf.add_page()
        self.state.set(style="B", font_size=constants.FONT_TITLE_SIZE)
        self.state.ln()
        self.state.write(self.title)
        self.state.ln()
        self.state.reset()

        if self.subtitle:
            self.state.set(font_size=constants.FONT_LARGE_SIZE + 10)
            self.state.write(self.subtitle)
            self.state.ln()
            self.state.reset()

        self.state.set(font_size=constants.FONT_LARGE_SIZE + 5)
        self.state.ln(0.5)
        for author in self.authors:
            self.state.write(author)
            if author != self.authors[-1]:
                self.state.write(", ")
        self.state.reset()
        self.state.ln(2)

        self.render(self.book.ast)

        if self.title_page_metadata:
            self.state.ln(2)
            self.state.write(f'{Tx("Status")}: {Tx(self.book.status)}')
            self.state.ln()
            now = datetime.datetime.now().strftime(constants.DATETIME_ISO_FORMAT)
            self.state.write(f'{Tx("Created")}: {now}')

    def write_toc(self, pdf, outline):
        h1 = constants.H_LOOKUP[1]
        font_size = h1["font"][1]
        pdf.set_font(style="B", size=font_size)
        pdf.cell(h=1.5 * font_size, text=Tx("Contents"))
        pdf.ln(1.5 * font_size)
        pdf.set_font(style="", size=constants.FONT_NORMAL_SIZE)

        self.state.set(line_height=1.1)
        with pdf.table(first_row_as_headings=False, borders_layout="none") as table:
            for section in outline[1:]:  # Skip "Contents" entry.
                link = pdf.add_link(page=section.page_number)
                row = table.row()
                row.cell(f'{" " * section.level * 2} {section.name}', link=link)
                row.cell(str(section.page_number), link=link)
        self.state.reset()

    def write_section(self, section, level):
        if level <= self.page_break_level:
            if self.skip_first_add_page:
                self.skip_first_add_page = False
            else:
                self.pdf.add_page()
        if level <= self.contents_level:
            self.pdf.start_section(section.heading, level=level - 1)
        self.write_heading(section.heading, level)
        for item in section.items:
            if item.is_section:
                self.write_section(item, level=level + 1)
            else:
                self.write_text(item, level=level + 1)

    def write_text(self, text, level):
        if level <= self.page_break_level:
            if self.skip_first_add_page:
                self.skip_first_add_page = False
            else:
                self.pdf.add_page()
        if level <= self.contents_level:
            self.pdf.start_section(text.heading, level=level - 1)
        if not text.frontmatter.get("suppress_title"):
            self.write_heading(text.heading, level)
        self.current_text = text
        self.render(text.ast)
        self.write_footnotes_text(text)

    def write_heading(self, heading, level, factor=1.5):
        level = min(level, constants.MAX_H_LEVEL)
        self.state.set(style="B", font_size=constants.H_LOOKUP[level]["font"][1])
        self.state.write(heading)
        self.state.ln(factor)
        self.state.reset()

    def write_footnotes_text(self, text):
        "Footnote definitions at the end of each text."
        if self.footnotes_location != constants.FOOTNOTES_EACH_TEXT:
            return
        try:
            footnotes = self.footnotes[text.fulltitle]
        except KeyError:
            return
        self.state.ln()
        self.write_heading(Tx("Footnotes"), 6)
        self.state.set(line_height=1.1)
        for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
            self.state.write(f"{entry['number']}. ")
            self.state.set(left_indent=20)
            for child in entry["ast_children"]:
                self.render(child)
            self.state.reset()
        self.state.reset()

    def write_footnotes_chapter(self, item):
        "Footnote definitions at the end of a chapter."
        if self.footnotes_location != constants.FOOTNOTES_EACH_CHAPTER:
            return
        try:
            footnotes = self.footnotes[item.chapter.fulltitle]
        except KeyError:
            return
        self.pdf.add_page()
        self.write_heading(Tx("Footnotes"), 4)
        self.state.set(line_height=1.1)
        for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
            self.state.write(f"{entry['number']}. ")
            self.state.set(left_indent=20)
            for child in entry["ast_children"]:
                self.render(child)
            self.state.reset()
        self.state.reset()

    def write_footnotes_book(self):
        "Footnote definitions as a separate section at the end of the book."
        if self.footnotes_location != constants.FOOTNOTES_END_OF_BOOK:
            return
        self.pdf.add_page()
        self.pdf.start_section(Tx("Footnotes"), level=0)
        self.write_heading(Tx("Footnotes"), 1)
        for item in self.source.items:
            footnotes = self.footnotes.get(item.fulltitle, {})
            if not footnotes:
                continue
            self.write_heading(item.heading, 2)
            self.state.set(line_height=1.1)
            for entry in sorted(footnotes.values(), key=lambda e: e["number"]):
                self.state.write(f"{entry['number']}. ")
                self.state.set(left_indent=20)
                for child in entry["ast_children"]:
                    self.render(child)
                self.state.reset()
            self.state.reset()

    def write_references(self):
        if not self.referenced:
            return
        self.pdf.add_page()
        self.pdf.start_section(Tx("References"), level=0)
        self.write_heading(Tx("References"), 1)
        for refid in sorted(self.referenced):
            try:
                reference = self.references[refid]
            except Error:
                continue
            self.state.set(style="B")
            self.state.write(reference["name"])
            self.state.reset()
            self.state.write("  ")
            self.write_reference_authors(reference)
            try:
                method = getattr(self, f"write_reference_{reference['type']}")
            except AttributeError:
                print("unknown", reference["type"])
            else:
                method(reference)
            self.write_reference_external_links(reference)
            self.state.ln(2)

    def write_reference_authors(self, reference):
        count = len(reference["authors"])
        for pos, author in enumerate(reference["authors"]):
            if pos > 0:
                if pos == count - 1:
                    self.state.write(" & ")
                else:
                    self.state.write(", ")
            self.state.write(utils.short_name(author))

    def write_reference_article(self, reference):
        "Write data for reference of type 'article'."
        self.state.write(f" ({reference['year']})")
        self.state.write(" " + utils.full_title(reference))
        journal = reference.get("journal")
        if journal:
            self.state.set(style="I")
            self.state.write(" " + journal)
            self.state.reset()
        try:
            self.state.write(" " + reference["volume"])
        except KeyError:
            pass
        else:
            try:
                self.state.write(f" ({reference['number']})")
            except KeyError:
                pass
        try:
            self.state.write(f": pp. {reference['pages'].replace('--', '-')}.")
        except KeyError:
            pass

    def write_reference_book(self, reference):
        "Write data for reference of type 'book'."
        self.state.write(f" ({reference['year']}).")
        self.state.set(style="I")
        self.state.write(" " + utils.full_title(reference))
        self.state.reset()
        try:
            self.state.write(f" {reference['publisher']}.")
        except KeyError:
            pass

    def write_reference_link(self, reference):
        "Write data for reference of type 'link'."
        self.state.write(f" ({reference['year']}).")
        title = utils.full_title(reference)
        self.state.write(" " + title)
        try:
            self.state.set(style="U", text_color=constants.PDF_HREF_COLOR)
            self.pdf.cell(
                h=self.state.line_height * self.state.font_size,
                text=title,
                link=reference["url"],
            )
            self.state.reset()
        except KeyError:
            pass
        try:
            self.state.write(f"Accessed {reference['accessed']}.")
        except KeyError:
            pass

    def write_reference_external_links(self, reference):
        links = []
        if reference.get("url"):
            links.append((reference["url"], reference["url"]))
        for key, (label, template) in constants.REFERENCE_LINKS.items():
            try:
                value = reference[key]
                text = f"{label}:{value}"
                url = template.format(value=value)
                links.append((text, url))
            except KeyError:
                pass
        if not links:
            return
        self.state.set(left_indent=20)
        self.state.ln()
        for pos, (text, url) in enumerate(links):
            if pos != 0:
                self.state.write(", ")
            self.state.set(style="U", text_color=constants.PDF_HREF_COLOR)
            self.pdf.cell(
                h=self.state.line_height * self.state.font_size,
                text=text,
                link=url,
                new_x=fpdf.enums.XPos.WCONT,
            )
            self.state.reset()
        self.state.reset()

    def write_indexed(self):
        if not self.indexed:
            return
        self.pdf.add_page()
        self.pdf.start_section(Tx("Index"), level=0)
        self.write_heading(Tx("Index"), 1)
        if self.indexed_xref == constants.PDF_PAGE_NUMBER:
            key = "page"
        elif self.indexed_xref == constants.PDF_TEXT_FULLTITLE:
            key = "fulltitle"
        elif self.indexed_xref == constants.PDF_TEXT_HEADING:
            key = "heading"
        else:
            return
        items = sorted(self.indexed.items(), key=lambda i: i[0].lower())
        for canonical, entries in items:
            self.state.write(canonical)
            self.state.write("  ")
            entries.sort(key=lambda e: e["ordinal"])
            for pos, entry in enumerate(entries):
                if pos != 0:
                    self.state.write(", ")
                self.state.set(style="U", text_color=constants.PDF_HREF_COLOR)
                self.pdf.cell(
                    h=self.state.line_height * self.state.font_size,
                    text=str(entry[key]),  # Page number is 'int'.
                    link=self.pdf.add_link(page=entry["page"]),
                    new_x=fpdf.enums.XPos.WCONT,
                )
                self.state.reset()
            self.state.ln()

    def render(self, ast):
        try:
            method = getattr(self, f"render_{ast['element']}")
        except AttributeError:
            print("Could not handle ast", ast)
        else:
            method(ast)

    def render_document(self, ast):
        for child in ast["children"]:
            self.render(child)

    def render_heading(self, ast):
        # XXX Limited implementation; just handles one child of raw text.
        text = ast["children"][0]["children"]
        self.write_heading(text, ast["level"])

    def render_paragraph(self, ast):
        for child in ast["children"]:
            self.render(child)
        if self.list_stack:
            if self.list_stack[-1]["tight"]:
                self.state.ln()
            else:
                self.state.ln(2)
        else:
            self.state.ln(2)

    def render_raw_text(self, ast):
        line = ast["children"]
        self.state.write(line)

    def render_blank_line(self, ast):
        pass

    def render_quote(self, ast):
        self.state.set(
            family=constants.QUOTE_FONT,
            font_size=constants.QUOTE_FONT_SIZE,
            left_indent=constants.QUOTE_LEFT_INDENT,
            right_indent=constants.QUOTE_RIGHT_INDENT,
        )
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_code_span(self, ast):
        self.state.set(family=constants.CODE_FONT)
        self.state.write(ast["children"])
        self.state.reset()

    def render_code_block(self, ast):
        self.state.set(
            family=constants.CODE_FONT,
            left_indent=constants.CODE_INDENT,
            line_height=1.2,
        )
        for child in ast["children"]:
            self.render(child)
        self.state.reset()
        self.state.ln()

    def render_fenced_code(self, ast):
        self.state.set(
            family=constants.CODE_FONT,
            left_indent=constants.CODE_INDENT,
            line_height=1.2,
        )
        for child in ast["children"]:
            self.render(child)
        self.state.reset()
        self.state.ln()

    def render_emphasis(self, ast):
        self.state.set(style="I")
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_strong_emphasis(self, ast):
        self.state.set(style="B")
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_superscript(self, ast):
        self.state.set(vertical="superscript")
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_subscript(self, ast):
        self.state.set(vertical="subscript")
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_emdash(self, ast):
        self.state.write(constants.EM_DASH)

    def render_line_break(self, ast):
        if ast.get("soft"):
            self.state.write(" ")
        else:
            self.state.ln()

    def render_thematic_break(self, ast):
        self.pdf.set_line_width(2)
        self.pdf.set_draw_color(r=128, g=128, b=128)
        width, height = self.pdf.default_page_dimensions
        self.pdf.line(
            x1=self.pdf.l_margin + constants.PDF_THEMATIC_BREAK_INDENT,
            y1=self.pdf.y,
            x2=width - (self.pdf.r_margin + constants.PDF_THEMATIC_BREAK_INDENT),
            y2=self.pdf.y,
        )
        self.state.ln()

    def render_link(self, ast):
        # XXX This handles only raw text within a link, nothing else.
        raw_text = []
        for child in ast["children"]:
            if child["element"] == "raw_text":
                raw_text.append(child["children"])
        self.state.set(style="U", text_color=constants.PDF_HREF_COLOR)
        self.pdf.cell(
            h=self.state.line_height * self.state.font_size,
            text="".join(raw_text),
            link=ast["dest"],
            new_x=fpdf.enums.XPos.WCONT,
        )
        self.state.reset()

    def render_list(self, ast):
        data = dict(
            ordered=ast["ordered"],
            bullet=ast["bullet"],  # Currently useless.
            start=ast["start"],  # Currently useless.
            tight=ast["tight"],
            depth=len(self.list_stack) + 1,
            count=0,
        )
        self.list_stack.append(data)
        self.state.set(line_height=1.1)
        for child in ast["children"]:
            self.render(child)
        self.state.reset()
        if self.list_stack[-1]["tight"]:
            self.state.ln()
        self.list_stack.pop()

    def render_list_item(self, ast):
        data = self.list_stack[-1]
        data["count"] += 1
        self.state.set(style="B")
        if data["ordered"]:
            self.state.write(f'{data["count"]}. ')
        else:
            self.state.write("- ")
        self.state.reset()
        self.state.set(left_indent=data["depth"] * constants.PDF_LIST_INDENT)
        for child in ast["children"]:
            self.render(child)
        self.state.reset()

    def render_indexed(self, ast):
        entries = self.indexed.setdefault(ast["canonical"], [])
        self.indexed_count += 1
        entries.append(
            dict(
                ordinal=self.current_text.ordinal,
                fulltitle=self.current_text.fulltitle,
                heading=self.current_text.heading,
                page=self.pdf.page_no(),
            )
        )
        self.state.set(style="U")
        self.state.write(ast["term"])
        self.state.reset()

    def render_footnote_ref(self, ast):
        # The label is used only for lookup; number is used for output.
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
        entries[key] = dict(label=label, number=number, page=self.pdf.page_no())
        self.state.set(vertical="superscript", style="B")
        self.state.write(str(number))
        self.state.reset()

    def render_footnote_def(self, ast):
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
        self.footnotes[fulltitle][key]["ast_children"] = ast["children"]

    def render_reference(self, ast):
        self.referenced.add(ast["id"])
        self.state.set(style="U")
        self.state.write(ast["name"])
        self.state.reset()


class Current:
    "Field providing the current value of the style parameter."

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        return obj.stack[-1][self.name]


class State:
    "Current style parameters state as a stack."

    family = Current()
    style = Current()
    font_size = Current()
    text_color = Current()
    line_height = Current()
    left_indent = Current()
    right_indent = Current()
    vertical = Current()

    def __init__(self, pdf):
        self.pdf = pdf
        self.stack = [
            dict(
                family=constants.FONT,
                style="",
                text_color=0,
                font_size=constants.FONT_NORMAL_SIZE,
                line_height=1.4,
                left_indent=0,
                right_indent=0,
                vertical=None,
            )
        ]
        self.pdf.set_font(family=self.family, style=self.style, size=self.font_size)
        self.l_margin = self.pdf.l_margin
        self.r_margin = self.pdf.r_margin

    def set(self, **kwargs):
        self.set_pdf_state(**kwargs)
        self.stack.append(self.stack[-1].copy())
        self.stack[-1].update(kwargs)

    def reset(self):
        diff = dict(
            [(k, v) for k, v in self.stack[-2].items() if self.stack[-1][k] != v]
        )
        self.stack.pop()
        self.set_pdf_state(**diff)

    def set_pdf_state(self, **kwargs):
        try:
            self.pdf.set_font(family=kwargs["family"])
        except KeyError:
            pass
        try:  # Due to apparent bug in fpdf2, set font_size before style.
            self.pdf.set_font(size=kwargs["font_size"])
        except KeyError:
            pass
        try:
            self.pdf.set_font(style=kwargs["style"])
        except KeyError:
            pass
        try:
            self.pdf.set_text_color(kwargs["text_color"])
        except KeyError:
            pass
        try:
            value = kwargs["left_indent"]
        except KeyError:
            pass
        else:
            self.pdf.set_left_margin(self.l_margin + value)
        try:
            value = kwargs["right_indent"]
        except KeyError:
            pass
        else:
            self.pdf.set_right_margin(self.l_margin + value)
        try:
            value = kwargs["vertical"]
        except KeyError:
            pass
        else:
            if value == "superscript":
                self.pdf.char_vpos = "SUP"
            elif value == "subscript":
                self.pdf.char_vpos = "SUB"
            else:
                self.pdf.char_vpos = "LINE"

    def write(self, text, link=""):
        self.pdf.write(h=self.font_size * self.line_height, text=text, link=link)

    def ln(self, factor=1):
        self.pdf.ln(factor * self.font_size * self.line_height)
