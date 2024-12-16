"""WriteThatBook
Write books in a web-based app using Markdown files allowing
references and indexing, creating DOCX or PDF.
"""

# import io
from http import HTTPStatus as HTTP

# import os
# from pathlib import Path
# import shutil
# import string
# import sys

from icecream import ic
import fasthtml
from fasthtml.common import *
import bibtexparser
import marko
import psutil
import requests
import yaml

import auth
import books, book_app
import components
import constants

# import docx_creator
# import pdf_creator
import utils
import users, user_app
from utils import Tx, Error


if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError("env var WRITETHATBOOK_DIR not defined: cannot execute")


def error_handler(request, exc):
    "Return a response with the message and status code."
    return Response(content=str(exc), status_code=exc.status_code)


app, rt = fast_app(
    live="WRITETHATBOOK_DEVELOPMENT" in os.environ,
    static_path="static",
    before=users.set_current_user,
    hdrs=(Link(rel="stylesheet", href="/mods.css", type="text/css"),),
    exception_handlers={
        Error: error_handler,
        auth.NotAllowed: auth.not_allowed_handler,
    },
    routes=[
        Mount("/book", book_app.app, name="book"),
        Mount("/user", user_app.app, name="user"),
    ],
)


@rt("/", name="home")
def get(request):
    "Home page; list of books."
    auth.authorize(request, auth.allow_all)

    hrows = Tr(
        Th(Tx("Title")),
        Th(Tx("Type")),
        Th(Tx("Status")),
        Th(Tx("Characters")),
        Th(Tx("Owner")),
        Th(Tx("Modified")),
    )
    # XXX filter allowed books
    allowed_books = books.get_books()
    rows = []
    for book in allowed_books:
        rows.append(
            Tr(
                Td(A(book.title, href=f"/book/{book.bid}")),
                Td(Tx(book.frontmatter.get("type", constants.BOOK).capitalize())),
                Td(
                    Tx(
                        book.frontmatter.get(
                            "status", repr(constants.STARTED)
                        ).capitalize()
                    )
                ),
                Td(Tx(utils.thousands(book.frontmatter.get("sum_characters", 0)))),
                Td(book.owner),
                Td(book.modified),
            )
        )
    menu = [components.references_link()]
    # if auth.logged_in(request):
    #     menu.append(A(Tx("Create or upload book"), href="/book"))
    # if auth.is_admin(request):
    #     menu.append(A(f'{Tx("Download")} {Tx("TGZ file")}', href="/tgz"))
    #     menu.append(A(Tx("State (JSON)"), href="/state"))
    #     if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
    #         menu.append(A(Tx("Differences"), href="/differences"))
    user = auth.logged_in(request)
    if user:
        menu.append(A(f'{Tx("User")} {user}', href=f"/user/view/{user.id}"))
    if auth.is_admin(request):
        menu.append(A(Tx("All users"), href="/user/list"))
    menu.append(A(Tx("System"), href="/system"))

    title = Tx("Books")
    return (
        Title(title),
        components.header(request, title, menu=menu),
        Main(Table(Thead(*hrows), Tbody(*rows)), cls="container"),
    )


@rt("/ping")
def get():
    "Health check."
    auth.authorize(request, auth.allow_all)
    return "It's alive!"


# @rt("/references")
# def get(request):
#     "List of references."
#     references = books.get_references()
#     references.write()  # Updates the 'index.md' file, if necessary.
#     items = []
#     for ref in references.items:
#         parts = [
#             Img(
#                 src="/clipboard.svg",
#                 title="Refid to clipboard",
#                 style="cursor: pointer;",
#                 cls="to_clipboard",
#                 data_clipboard_text=f'[@{ref["name"]}]',
#             ),
#             components.blank(0.2),
#             A(
#                 Strong(ref["name"], style=f"color: {constants.REFERENCE_COLOR};"),
#                 href=f'/reference/{ref["id"]}',
#             ),
#             components.blank(0.4),
#         ]
#         if ref.get("authors"):
#             authors = [utils.short_name(a) for a in ref["authors"]]
#             if len(authors) > constants.MAX_DISPLAY_AUTHORS:
#                 authors = authors[: constants.MAX_DISPLAY_AUTHORS] + ["..."]
#             parts.append(", ".join(authors))
#         parts.append(Br())
#         parts.append(utils.full_title(ref))

#         links = []
#         if ref["type"] == constants.ARTICLE:
#             parts.append(Br())
#             if ref.get("journal"):
#                 parts.append(I(ref["journal"]))
#             if ref.get("volume"):
#                 parts.append(f' {ref["volume"]}')
#             if ref.get("number"):
#                 parts.append(f' ({ref["number"]})')
#             if ref.get("pages"):
#                 parts.append(f' {ref["pages"].replace("--", "-")}')
#             if ref.get("year"):
#                 parts.append(f' ({ref["year"]})')
#             if ref.get("edition_published"):
#                 parts.append(f' [{ref["edition_published"]}]')
#         elif ref["type"] == constants.BOOK:
#             parts.append(Br())
#             if ref.get("publisher"):
#                 parts.append(f'{ref["publisher"]}')
#             # Edition published later than original publication.
#             if ref.get("edition_published"):
#                 parts.append(f' {ref["edition_published"]}')
#                 if ref.get("year"):
#                     parts.append(f' [{ref["year"]}]')
#             # Standard case; publication and edition same year.
#             elif ref.get("year"):
#                 parts.append(f' {ref["year"]}')
#             if ref.get("isbn"):
#                 symbol, url = constants.REFERENCE_LINKS["isbn"]
#                 url = url.format(value=ref["isbn"])
#                 if links:
#                     links.append(", ")
#                 links.append(
#                     A(f'{symbol}:{ref["isbn"]}', href=url.format(value=ref["isbn"]))
#                 )
#         elif ref["type"] == constants.LINK:
#             parts.append(Br())
#             if ref.get("publisher"):
#                 parts.append(f'{ref["publisher"]}')
#             if ref.get("year"):
#                 parts.append(f' ({ref["year"]})')

#         if ref.get("url"):
#             parts.append(Br())
#             parts.append(A(ref["url"], href=ref["url"]))
#             if ref.get("accessed"):
#                 parts.append(f' (Accessed: {ref["accessed"]})')
#         if ref.get("doi"):
#             symbol, url = constants.REFERENCE_LINKS["doi"]
#             url = url.format(value=ref["doi"])
#             if links:
#                 links.append(", ")
#             links.append(A(f'{symbol}:{ref["doi"]}', href=url.format(value=ref["doi"])))
#         if ref.get("pmid"):
#             symbol, url = constants.REFERENCE_LINKS["pmid"]
#             url = url.format(value=ref["pmid"])
#             if links:
#                 links.append(", ")
#             links.append(
#                 A(f'{symbol}:{ref["pmid"]}', href=url.format(value=ref["pmid"]))
#             )

#         if links:
#             parts.append(" ")
#             parts.extend(links)

#         xrefs = []
#         for book in books.get_books():
#             texts = book.references.get(ref["id"], [])
#             for text in sorted(texts, key=lambda t: t.ordinal):
#                 if xrefs:
#                     xrefs.append(Br())
#                 xrefs.append(
#                     A(
#                         f"{book.title}: {text.fulltitle}",
#                         cls="secondary",
#                         href=f"/book/{book.bid}/{text.path}",
#                     )
#                 )
#         if xrefs:
#             parts.append(Small(Br(), *xrefs))

#         items.append(P(*parts, id=ref["name"]))

#     menu = [A(Tx("Keywords"), href="/references/keywords")]
#     menu.extend(
#         [
#             A(Tx(f'{Tx("Add reference")}: {Tx(type)}'), href=f"/reference/add/{type}")
#             for type in constants.REFERENCE_TYPES
#         ]
#     )
#     menu.append(A(f'{Tx("Add reference")}: BibTex', href="/reference/bibtex"))
#     menu.append(components.statuslist_link(references)),
#     menu.append(A(Tx("Recently modified"), href="/recent/references"))
#     menu.append(
#         A(
#             f'{Tx("Download")} {Tx("references")} {Tx("TGZ file")}',
#             href="/tgz/references",
#         )
#     )
#     menu.append(
#         A(
#             f'{Tx("Upload")} {Tx("references")} {Tx("TGZ file")}',
#             href="/references/upload",
#         )
#     )
#     menu.append(A(Tx("State (JSON)"), href="/state/references"))
#     if "MDBOOK_UPDATE_SITE" in os.environ:
#         menu.append(A(Tx("Differences"), href="/differences/references"))

#     title = f'{Tx("References")} ({len(references.items)})'
#     return (
#         Title(title),
#         components.header(request, title, menu=menu),
#         Main(components.search_form(f"/search/references"), *items, cls="container"),
#     )


# @rt("/references/keywords")
# def get():
#     "List the keyword terms of the references."
#     book = books.get_references()
#     items = []
#     for key, texts in sorted(book.indexed.items(), key=lambda tu: tu[0].lower()):
#         refs = []
#         for text in sorted(texts, key=lambda t: t.ordinal):
#             refs.append(
#                 Li(
#                     A(
#                         f'{text["name"]}: {text.fulltitle}',
#                         cls="secondary",
#                         href=f"/reference/{text.path}",
#                     )
#                 )
#             )
#         items.append(Li(key, Small(Ul(*refs))))

#     menu = [components.references_link()]

#     title = f'{Tx("Keywords")}, {Tx("references")}'
#     return (
#         Title(title),
#         components.header(request, title, menu=menu),
#         Main(Ul(*items), cls="container"),
#     )


# @rt("/references/upload")
# def get():
#     "Upload a gzipped tar file of references; replace any reference with the same name."
#     title = Tx("Upload references")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 Input(type="file", name="tgzfile"),
#                 Button(f'{Tx("Upload")} {Tx("TGZ file")}'),
#                 action="/references/upload",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/references/upload")
# async def post(tgzfile: UploadFile):
#     "Actually add or replace references by contents of the uploaded file."
#     utils.unpack_tgzfile(
#         Path(os.environ["MDBOOK_DIR"]) / constants.REFERENCES,
#         await tgzfile.read(),
#         references=True,
#     )
#     books.get_references(refresh=True)

#     return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)


# @rt("/reference/add/{type:str}")
# def get(type: str):
#     "Add reference from scratch."
#     title = f'{Tx("Add reference")}: {Tx(type)}'
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 *components.get_reference_fields(type=type),
#                 Button(Tx("Save")),
#                 action=f"/reference",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/reference")
# def post(form: dict):
#     "Actually add reference from scratch."
#     reference = components.get_reference_from_form(form)
#     books.get_references(refresh=True)

#     return RedirectResponse(f"/reference/{reference['id']}", status_code=HTTP.SEE_OTHER)


# @rt("/reference/bibtex")
# def get():
#     "Add reference(s) from BibTex data."
#     title = f'{Tx("Add reference")}: BibTex'
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 Fieldset(
#                     Legend(Tx("BibTex data")),
#                     Textarea(name="data", rows="20", autofocus=True),
#                 ),
#                 Button("Add"),
#                 action="/reference/bibtex",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/reference/bibtex")
# def post(data: str):
#     "Actually add reference(s) using BibTex data."
#     result = []
#     for entry in bibtexparser.loads(data).entries:
#         form = {
#             "authors": utils.cleanup_latex(entry["author"]).replace(" and ", "\n"),
#             "year": entry["year"],
#             "type": entry.get("ENTRYTYPE") or constants.ARTICLE,
#         }
#         for key, value in entry.items():
#             if key in ("author", "ID", "ENTRYTYPE"):
#                 continue
#             form[key] = utils.cleanup_latex(value).strip()
#         # Do some post-processing.
#         # Change month into date; sometimes has day number.
#         month = form.pop("month", "")
#         parts = month.split("~")
#         if len(parts) == 2:
#             month = constants.MONTHS[parts[1].strip().lower()]
#             day = int("".join([c for c in parts[0] if c in string.digits]))
#             form["date"] = f'{entry["year"]}-{month:02d}-{day:02d}'
#         elif len(parts) == 1:
#             month = constants.MONTHS[parts[0].strip().lower()]
#             form["date"] = f'{entry["year"]}-{month:02d}-00'
#         # Change page numbers double dash to single dash.
#         form["pages"] = form.get("pages", "").replace("--", "-")
#         # Put abstract into notes.
#         abstract = form.pop("abstract", None)
#         if abstract:
#             form["notes"] = "**Abstract**\n\n" + abstract
#         try:
#             reference = components.get_reference_from_form(form)
#         except Error:
#             pass
#         else:
#             result.append(reference)

#     # Refresh the cache.
#     references = books.get_references(refresh=True)

#     title = Tx("Added reference(s)")
#     return (
#         Title(title),
#         components.header(request, title, book=references),
#         Main(
#             Ul(*[Li(A(r["name"], href=f'/reference/{r["id"]}')) for r in result]),
#             cls="container",
#         ),
#     )


# @rt("/reference/{refid:str}")
# def get(refid: str):
#     "Display a reference."
#     if not refid:
#         return RedirectResponse(f"/references", status_code=HTTP.SEE_OTHER)

#     references = books.get_references()
#     try:
#         ref = references[refid]
#     except KeyError:
#         raise Error(f"no such reference '{refid}'", HTTP.NOT_FOUND)
#     rows = [
#         Tr(
#             Td(Tx("Reference")),
#             Td(
#                 f'{ref["name"]}',
#                 components.blank(0.2),
#                 Img(
#                     src="/clipboard.svg",
#                     title=Tx("Reference to clipboard"),
#                     style="cursor: pointer;",
#                     cls="to_clipboard",
#                     data_clipboard_text=f'[@{ref["name"]}]',
#                 ),
#             ),
#         ),
#         Tr(Td(Tx("Authors"), valign="top"), Td("; ".join(ref.get("authors") or []))),
#     ]
#     for key in [
#         "title",
#         "subtitle",
#         "year",
#         "edition_published",
#         "date",
#         "journal",
#         "volume",
#         "number",
#         "pages",
#         "language",
#         "publisher",
#     ]:
#         value = ref.get(key)
#         if value:
#             rows.append(
#                 Tr(Td((Tx(key.replace("_", " ")).title()), valign="top"), Td(value))
#             )
#     if ref.get("keywords"):
#         rows.append(
#             Tr(Td(Tx("Keywords"), valign="top"), Td("; ".join(ref["keywords"])))
#         )
#     if ref.get("issn"):
#         rows.append(Tr(Td("ISSN"), Td(ref["issn"])))
#     if ref.get("isbn"):
#         url = constants.REFERENCE_LINKS["isbn"][1].format(value=ref["isbn"])
#         rows.append(Tr(Td("ISBN"), Td(A(ref["isbn"], href=url))))
#     if ref.get("pmid"):
#         url = constants.REFERENCE_LINKS["pmid"][1].format(value=ref["pmid"])
#         rows.append(Tr(Td("PubMed"), Td(A(ref["pmid"], href=url))))
#     if ref.get("doi"):
#         url = constants.REFERENCE_LINKS["doi"][1].format(value=ref["doi"])
#         rows.append(Tr(Td("DOI"), Td(A(ref["doi"], href=url))))
#     if ref.get("url"):
#         rows.append(Tr(Td("Url"), Td(A(ref["url"], href=ref["url"]))))
#     xrefs = []
#     for book in books.get_books():
#         texts = book.references.get(ref["id"], [])
#         for text in sorted(texts, key=lambda t: t.ordinal):
#             if xrefs:
#                 xrefs.append(Br())
#             xrefs.append(
#                 A(
#                     f"{book.title}: {text.fulltitle}",
#                     href=f"/book/{book.bid}/{text.path}",
#                 )
#             )
#     rows.append(Tr(Td(Tx("Referenced by"), valign="top"), Td(*xrefs)))

#     menu = [
#         A(
#             Tx("Clipboard"),
#             href="#",
#             cls="to_clipboard",
#             data_clipboard_text=f'[@{ref["name"]}]',
#         ),
#         components.references_link(),
#         A(Tx("Edit"), href=f"/reference/edit/{refid}"),
#         A(Tx("Append"), href=f"/append/references/{refid}"),
#         A(Tx("Delete"), href=f"/delete/references/{refid}"),  # Yes, plural.
#     ]

#     title = f'{ref["name"]} ({Tx(ref["type"])})'
#     edit_buttons = Div(
#         Div(A(Tx("Edit"), role="button", href=f"/reference/edit/{refid}")),
#         Div(A(Tx("Append"), role="button", href=f"/append/references/{refid}")),
#         cls="grid",
#     )
#     return (
#         Title(title),
#         Script(src="/clipboard.min.js"),
#         Script("new ClipboardJS('.to_clipboard');"),
#         components.header(request, title, book=references, status=ref.status, menu=menu),
#         Main(
#             Table(*rows),
#             edit_buttons,
#             Div(NotStr(ref.html), style="margin-top: 1em;"),
#             edit_buttons,
#             cls="container",
#         ),
#         components.footer(ref),
#     )


# @rt("/reference/edit/{refid:str}")
# def get(refid: str):
#     "Edit a reference."
#     reference = books.get_references()[refid]

#     title = f"{Tx('Edit')} '{reference['name']}' ({Tx(reference['type'])})"
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 *components.get_reference_fields(ref=reference, type=reference["type"]),
#                 components.get_status_field(reference),
#                 Button(Tx("Save")),
#                 action=f"/reference/edit/{refid}",
#                 method="post",
#             ),
#             components.cancel_button(f"/reference/{refid}"),
#             cls="container",
#         ),
#     )


# @rt("/reference/edit/{refid:str}")
# def post(refid: str, form: dict):
#     "Actually edit the reference."
#     reference = books.get_references()[refid]
#     try:
#         reference.status = form.pop("status")
#     except KeyError:
#         pass
#     components.get_reference_from_form(form, ref=reference)
#     books.get_references(refresh=True)

#     return RedirectResponse(f"/reference/{refid}", status_code=HTTP.SEE_OTHER)


# @rt("/book")
# def get():
#     "Create and/or upload book using a gzipped tar file."
#     title = Tx("Create or upload book")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Form(
#                 Fieldset(
#                     Legend(Tx("Title")),
#                     Input(name="title", required=True, autofocus=True),
#                 ),
#                 Fieldset(
#                     Legend(Tx(f'{Tx("Upload")} {Tx("TGZ file")} ({Tx("optional")}).')),
#                     Input(type="file", name="tgzfile"),
#                 ),
#                 Button(Tx("Create")),
#                 action="/book",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/book")
# async def post(auth, title: str, tgzfile: UploadFile):
#     "Actually create and/or upload book using a gzipped tar file."
#     if not title:
#         raise Error("book title may not be empty", HTTP.BAD_REQUEST)
#     if title.startswith("_"):
#         raise Error("book title may not start with an underscore '_'", HTTP.BAD_REQUEST)
#     bid = utils.nameify(title)
#     if not bid:
#         raise Error("book bid may not be empty", HTTP.BAD_REQUEST)
#     dirpath = Path(os.environ["MDBOOK_DIR"]) / bid
#     if dirpath.exists():
#         raise Error(f"book {bid} already exists", HTTP.CONFLICT)

#     content = await tgzfile.read()
#     if content:
#         try:
#             utils.unpack_tgzfile(dirpath, content)
#         except ValueError as message:
#             raise Error(f"error reading TGZ file: {message}", HTTP.BAD_REQUEST)
#     # Just create the directory; no content.
#     else:
#         dirpath.mkdir()

#     # Re-read all books, ensuring everything is up to date.
#     books.read_books()
#     # Set the title and owner of the new book.
#     book = books.get_book(bid)
#     book.frontmatter["title"] = title or book.title
#     book.frontmatter["owner"] = auth
#     book.write()

#     return RedirectResponse(f"/book/{book.bid}", status_code=HTTP.SEE_OTHER)


# @rt("/book/{bid:str}")
# def get(bid: str):
#     "Display book; contents list of sections and texts."
#     if bid == constants.REFERENCES:
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)

#     book = books.get_book(bid)
#     book.write()  # Updates the 'index.md' file, if necessary.

#     menu = [
#         A(Tx("Edit"), href=f"/edit/{bid}"),
#         A(Tx("Append"), href=f"/append/{bid}/"),
#         A(f'{Tx("Create")} {Tx("section")}', href=f"/section/{bid}"),
#         A(f'{Tx("Create")} {Tx("text")}', href=f"/text/{bid}"),
#         A(Tx("Recently modified"), href=f"/recent/{bid}"),
#         components.index_link(book),
#         components.statuslist_link(book),
#         components.references_link(),
#         A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/docx/{bid}"),
#         A(f'{Tx("Download")} {Tx("PDF file")}', href=f"/pdf/{bid}"),
#         A(f'{Tx("Download")} {Tx("TGZ file")}', href=f"/tgz/{bid}"),
#         A(Tx("Information"), href=f"/information/{bid}"),
#         A(Tx("State (JSON)"), href=f"/state/{bid}"),
#     ]
#     if "MDBOOK_UPDATE_SITE" in os.environ:
#         menu.append(A(f'{Tx("Differences")}', href=f"/differences/{bid}"))
#     menu.append(A(f'{Tx("Copy")}', href=f"/copy/{bid}"))
#     menu.append(A(f'{Tx("Delete")}', href=f"/delete/{bid}"))

#     segments = [components.search_form(f"/search/{bid}")]

#     if len(book.items) == 0:
#         segments.append(H3(book.title))
#         if book.subtitle:
#             segments.append(H4(book.subtitle))
#         for author in book.authors:
#             segments.append(H5(author))
#     else:
#         segments.append(components.toc(book, book.items, show_arrows=True))

#     return (
#         Title(book.title),
#         components.header(request, Tx("Contents"), book=book, menu=menu, status=book.status),
#         Main(
#             *segments,
#             Div(NotStr(book.html)),
#             Div(
#                 Div(A(Tx("Edit"), role="button", href=f"/edit/{bid}")),
#                 Div(A(Tx("Append"), role="button", href=f"/append/{bid}/")),
#                 cls="grid",
#             ),
#             cls="container",
#         ),
#         components.footer(book),
#     )


# @rt("/edit/{bid:str}")
# def get(bid: str):
#     "Edit the book data."
#     book = books.get_book(bid)

#     fields = [
#         Fieldset(
#             Legend(Tx("Title")),
#             Input(
#                 name="title",
#                 value=book.frontmatter["title"],
#                 required=True,
#                 autofocus=True,
#             ),
#         ),
#         Fieldset(
#             Legend(Tx("Subtitle")),
#             Input(name="subtitle", value=book.frontmatter.get("subtitle", "")),
#         ),
#         Fieldset(
#             Legend(Tx("Authors")),
#             Textarea(
#                 "\n".join(book.frontmatter.get("authors", [])),
#                 name="authors",
#                 rows="10",
#             ),
#         ),
#     ]
#     if len(book.items) == 0:
#         fields.append(
#             Fieldset(
#                 Legend(Tx("Status")),
#                 components.get_status_field(book),
#             )
#         )
#     language_options = []
#     for language in constants.LANGUAGE_CODES:
#         if book.frontmatter.get("language") == language:
#             language_options.append(Option(language, selected=True))
#         else:
#             language_options.append(Option(language))
#     fields.append(
#         Fieldset(Legend(Tx("Language")), Select(*language_options, name="language"))
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Text")),
#             Textarea(
#                 NotStr(book.content),
#                 name="content",
#                 rows="10",
#             ),
#         )
#     )
#     menu = [components.references_link()]

#     title = f'{Tx("Edit")} {Tx("book")}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, menu=menu, status=book.status),
#         Main(
#             Form(*fields, Button(Tx("Save")), action=f"/edit/{bid}", method="post"),
#             components.cancel_button(f"/book/{bid}"),
#             cls="container",
#         ),
#     )


# @rt("/edit/{bid:str}")
# def post(bid: str, form: dict):
#     "Actually edit the book data."
#     book = books.get_book(bid)
#     try:
#         title = form["title"].strip()
#         if not title:
#             raise KeyError
#         book.frontmatter["title"] = title
#     except KeyError:
#         raise Error("no title given for book", HTTP.BAD_REQUEST)
#     book.frontmatter["authors"] = [
#         a.strip() for a in form.get("authors", "").split("\n")
#     ]
#     for key in ["subtitle", "status", "language"]:
#         value = form.get(key, "").strip()
#         if value:
#             book.frontmatter[key] = value
#         else:
#             book.frontmatter.pop(key, None)

#     # Refresh the book, ensuring everything is up to date.
#     book.write(content=form.get("content"), force=True)
#     book.read()

#     return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/copy/{bid:str}")
# def get(auth, bid: str):
#     "Make a copy of the book."
#     book = books.get_book(bid)
#     new = book.copy(owner=auth)

#     return RedirectResponse(f"/book/{new.bid}", status_code=HTTP.SEE_OTHER)


# @rt("/delete/{bid:str}")
# def get(bid: str):
#     "Confirm deleting book."
#     book = books.get_book(bid)

#     if book.items or book.content:
#         segments = [P(Strong(Tx("Note: all contents will be lost!")))]
#     else:
#         segments = []

#     title = f"{Tx('Delete book')} '{book.title}'?"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status),
#         Main(
#             H3(Tx("Delete"), "?"),
#             *segments,
#             Form(Button(Tx("Confirm")), action=f"/delete/{bid}", method="post"),
#             components.cancel_button(f"/book/{bid}"),
#             cls="container",
#         ),
#     )


# @rt("/delete/{bid:str}")
# def post(bid: str):
#     "Actually delete the book, even if it contains items."
#     book = books.get_book(bid)
#     book.delete(force=True)

#     return RedirectResponse("/", status_code=HTTP.SEE_OTHER)


# @rt("/search/{bid:str}")
# def post(bid: str, form: dict):
#     "Actually search the book for a given term."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     term = form.get("term")
#     if term:
#         items = [
#             Li(A(i.fulltitle, href=f"/book/{bid}/{i.path}"))
#             for i in sorted(
#                 book.search(
#                     utils.wildcard_to_regexp(term), ignorecase=term == term.lower()
#                 ),
#                 key=lambda i: i.ordinal,
#             )
#         ]
#         if items:
#             result = P(Ul(*items))
#         else:
#             result = P(f'{Tx("No result")}.')
#     else:
#         result = P()

#     menu = [components.index_link(book)]
#     if bid != constants.REFERENCES:
#         menu.append(components.references_link())

#     title = f'{Tx("Search")} {Tx("book")}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status, menu=menu),
#         Main(
#             components.search_form(f"/search/{bid}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/recent/{bid:str}")
# def get(bid: str):
#     "Display the most recently modified items in the book."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)

#     items = book.all_items
#     items.sort(key=lambda i: i.modified, reverse=True)
#     items = items[: constants.MAX_RECENT]

#     menu = [components.index_link(book)]

#     if bid == constants.REFERENCES:
#         menu.append(components.references_link())
#         rows = [
#             Tr(
#                 Td(A(i["name"], href=f"/reference/{i.path}"), ": ", i.fulltitle),
#                 Td(i.modified),
#             )
#             for i in items
#         ]
#     else:
#         rows = [
#             Tr(Td(A(i.fulltitle, href=f"/book/{bid}/{i.path}")), Td(i.modified))
#             for i in items
#         ]

#     title = Tx("Recently modified")
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status, menu=menu),
#         Main(
#             P(Table(Tbody(*rows))),
#             cls="container",
#         ),
#     )


# @rt("/book/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "View of book text or section contents."
#     if bid == constants.REFERENCES:
#         return RedirectResponse(f"/reference/{path}", status_code=HTTP.SEE_OTHER)

#     if not path:
#         return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)

#     book = books.get_book(bid)
#     item = book[path]

#     menu = []
#     if item.parent:
#         if item.parent.level == 0:  # Book.
#             url = f"/book/{book.bid}"
#         else:
#             url = f"/book/{book.bid}/{item.parent.path}"
#         menu.append(A(NotStr(f"&ShortUpArrow; {item.parent.title}"), href=url))
#     if item.prev:
#         url = f"/book/{book.bid}/{item.prev.path}"
#         menu.append(A(NotStr(f"&ShortLeftArrow; {item.prev.title}"), href=url))
#     if item.next:
#         url = f"/book/{book.bid}/{item.next.path}"
#         menu.append(A(NotStr(f"&ShortRightArrow; {item.next.title}"), href=url))

#     menu.append(A(Tx("Edit"), href=f"/edit/{bid}/{path}"))
#     menu.append(A(Tx("Append"), href=f"/append/{bid}/{path}"))

#     if item.is_text:
#         menu.append(A(Tx("Convert to section"), href=f"/to_section/{bid}/{path}"))
#         menu.append(
#             A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/docx/{bid}/{path}")
#         )
#         segments = [H3(item.heading)]

#     elif item.is_section:
#         menu.append(A(f'{Tx("Create")} {Tx("section")}', href=f"/section/{bid}/{path}"))
#         menu.append(A(f'{Tx("Create")} {Tx("text")}', href=f"/text/{bid}/{path}"))
#         menu.append(
#             A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/docx/{bid}/{path}")
#         )
#         segments = [
#             Div(
#                 Div(H3(item.heading)),
#                 Div(components.search_form(f"/search/{bid}/{path}")),
#                 cls="grid",
#             ),
#             components.toc(book, item.items),
#         ]

#     menu.append(components.index_link(book))
#     menu.append(components.references_link())
#     menu.append(A(f'{Tx("Copy")}', href=f"/copy/{bid}/{path}"))
#     menu.append(A(f'{Tx("Delete")}', href=f"/delete/{bid}/{path}"))

#     edit_buttons = Div(
#         Div(A(Tx("Edit"), role="button", href=f"/edit/{bid}/{path}")),
#         Div(A(Tx("Append"), role="button", href=f"/append/{bid}/{path}")),
#         cls="grid",
#     )

#     return (
#         Title(item.title),
#         components.header(request, item.title, book=book, menu=menu, status=item.status),
#         Main(
#             *segments,
#             edit_buttons,
#             Div(NotStr(item.html), style="margin-top: 1em;"),
#             edit_buttons,
#             cls="container",
#         ),
#         components.footer(item),
#     )


# @rt("/edit/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Edit the item (section or text)."
#     book = books.get_book(bid)
#     item = book[path]

#     title_field = Fieldset(
#         Label(Tx("Title")),
#         Input(name="title", value=item.title, required=True, autofocus=True),
#     )
#     if item.is_text:
#         item.read()
#         fields = [
#             Div(
#                 title_field,
#                 Fieldset(
#                     Legend(Tx("Status")),
#                     components.get_status_field(item),
#                 ),
#                 cls="grid",
#             )
#         ]
#     elif item.is_section:
#         fields = [title_field]
#     fields.append(
#         Fieldset(
#             Legend(Tx("Text")),
#             Textarea(NotStr(item.content), name="content", rows="20"),
#         )
#     )

#     title = f"{Tx('Edit')} '{item.title}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=item.status),
#         Main(
#             Form(
#                 *fields, Button(Tx("Save")), action=f"/edit/{bid}/{path}", method="post"
#             ),
#             components.cancel_button(f"/book/{bid}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/edit/{bid:str}/{path:path}")
# def post(bid: str, path: str, title: str, content: str, status: str = None):
#     "Actually edit the item (section or text)."
#     book = books.get_book(bid)
#     item = book[path]
#     item.title = title
#     item.name = title  # Changes name of directory/file.
#     if item.is_text:
#         if status is not None:
#             item.status = status
#     item.write(content=content)

#     # Refresh the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/book/{bid}/{item.path}", status_code=HTTP.SEE_OTHER)


# @rt("/append/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Append to the content of an item."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     if path:
#         item = book[path]
#     else:
#         item = book

#     title = f'{Tx("Append")} {item.title}'
#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Form(
#                 Textarea(name="content", rows="20", autofocus=True),
#                 Button(Tx("Append")),
#                 action=f"/append/{bid}/{path}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{bid}/{path}"),  # This works for all.
#             cls="container",
#         ),
#     )


# @rt("/append/{bid:str}/{path:path}")
# def post(bid: str, path: str, content: str):
#     "Actually append to the content of an item."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     if path:
#         item = book[path]
#     else:
#         item = book

#     # Slot in appended content before footnotes, if any.
#     lines = item.content.split("\n")
#     for pos, line in enumerate(lines):
#         if line.startswith("[^"):
#             lines.insert(pos - 1, content + "\n")
#             break
#     else:
#         lines.append(content)
#     item.write(content="\n".join(lines))

#     # Refresh the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/append/{bid}/{path}", status_code=HTTP.SEE_OTHER)


# @rt("/search/{bid:str}/{path:path}")
# def post(bid: str, path: str, form: dict):
#     "Actually search the item (text or section)  for a given term."
#     book = books.get_book(bid)
#     item = book[path]
#     term = form.get("term")
#     if term:
#         items = [
#             Li(A(i.fulltitle, href=i.path))
#             for i in sorted(
#                 item.search(
#                     utils.wildcard_to_regexp(term), ignorecase=term == term.lower()
#                 ),
#                 key=lambda i: i.ordinal,
#             )
#         ]
#         if items:
#             result = P(Ul(*items))
#         else:
#             result = P(f'{Tx("No result")}.')
#     else:
#         result = P()

#     title = f"{Tx('Search')} '{item.fulltitle}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=item.status),
#         Main(
#             components.search_form(f"/search/{bid}/{path}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/forward/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Move item forward in its sibling list."
#     books.get_book(bid)[path].forward()
#     return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/backward/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Move item backward in its sibling list."
#     books.get_book(bid)[path].backward()
#     return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/outof/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Move item out of its section."
#     books.get_book(bid)[path].outof()
#     return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/into/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Move item into the nearest preceding section."
#     book = books.get_book(bid)[path].into()
#     return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/copy/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Make a copy of the item (text or section)."
#     path = books.get_book(bid)[path].copy()
#     return RedirectResponse(f"/book/{bid}/{path}", status_code=HTTP.SEE_OTHER)


# @rt("/delete/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Confirm delete of the text or section; section must be empty."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     item = book[path]
#     if len(item.items) != 0 or item.content:
#         segments = [P(Strong(Tx("Note: all contents will be lost!")))]
#     else:
#         segments = []

#     if bid == constants.REFERENCES:
#         title = f"{Tx('Delete')} {Tx('reference')} '{item['name']}'?"
#     else:
#         title = f"{Tx('Delete')} {Tx(item.type)} '{item.fulltitle}'?"

#     return (
#         Title(title),
#         components.header(request, title, book=book, status=item.status),
#         Main(
#             H3(Tx("Delete"), "?"),
#             *segments,
#             Form(Button(Tx("Confirm")), action=f"/delete/{bid}/{path}", method="post"),
#             components.cancel_button(f"/book/{bid}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/delete/{bid:str}/{path:path}")
# def post(bid: str, path: str):
#     "Delete the text or section."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     item = book[path]
#     item.delete(force=True)

#     if bid == constants.REFERENCES:
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)
#     else:
#         return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/to_section/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Convert to section containing a text with this text."
#     book = books.get_book(bid)
#     text = book[path]
#     assert text.is_text

#     title = f"{Tx('Convert to section')}: '{text.fulltitle}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=text.status),
#         Main(
#             Form(
#                 Button(Tx("Convert")), action=f"/to_section/{bid}/{path}", method="post"
#             ),
#             components.cancel_button(f"/book/{bid}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/to_section/{bid:str}/{path:path}")
# def post(bid: str, path: str):
#     "Actually convert to section containing a text with this text."
#     book = books.get_book(bid)
#     text = book[path]
#     assert text.is_text
#     section = text.to_section()

#     # Refresh the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/book/{bid}/{section.path}", status_code=HTTP.SEE_OTHER)


# @rt("/text/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Create a new text in the section."
#     book = books.get_book(bid)
#     if path:
#         parent = book[path]
#         assert parent.is_section
#         title = f"{Tx('Create text in')} '{parent.fulltitle}'"
#     else:
#         title = f"{Tx('Create text in')} {Tx('book')}"

#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Form(
#                 Fieldset(
#                     Label(Tx("Title")),
#                     Input(name="title", required=True, autofocus=True),
#                 ),
#                 Button(Tx("Create")),
#                 action=f"/text/{bid}/{path}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{bid}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/text/{bid:str}/{path:path}")
# def post(bid: str, path: str, title: str = None):
#     "Actually create a new text in the section."
#     book = books.get_book(bid)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_text(title, parent=parent)

#     # Refresh the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{bid}/{new.path}", status_code=HTTP.SEE_OTHER)


# @rt("/section/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Create a new section in the section."
#     book = books.get_book(bid)
#     if path:
#         parent = book[path]
#         assert parent.is_section
#         title = f"{Tx('Create section in')} '{parent.fulltitle}'"
#     else:
#         title = f"{Tx('Create section in')} {Tx('book')}"

#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Form(
#                 Fieldset(
#                     Label(Tx("Title")),
#                     Input(name="title", required=True, autofocus=True),
#                 ),
#                 Button(Tx("Create")),
#                 action=f"/section/{bid}/{path}",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/section/{bid:str}/{path:path}")
# def post(bid: str, path: str, title: str = None):
#     "Actually create a new section in the section."
#     book = books.get_book(bid)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_section(title, parent=parent)

#     # Refresh the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{bid}/{new.path}", status_code=HTTP.SEE_OTHER)


# @rt("/information/{bid:str}")
# def get(bid: str):
#     "Display information about the book."
#     book = books.get_book(bid)

#     segments = [H3(book.title)]
#     if book.subtitle:
#         segments.append(H4(book.subtitle))
#     for author in book.authors:
#         segments.append(H5(author))
#     segments.append(P(f'{Tx("Type")}: {Tx(book.type.capitalize())}'))
#     segments.append(P(f'{Tx("Status")}: {Tx(book.status)}'))
#     segments.append(P(f'{Tx("Owner")}: {Tx(book.owner)}'))
#     segments.append(P(f'{Tx("Modified")}: {book.modified}'))
#     segments.append(P(f'{Tx("Words")}: {utils.thousands(book.sum_words)}'))
#     segments.append(P(f'{Tx("Characters")}: {utils.thousands(book.sum_characters)}'))
#     segments.append(P(f'{Tx("Language")}: {book.frontmatter.get("language") or "-"}'))

#     menu = [
#         A(f'{Tx("Edit")}', href=f"/edit/{bid}"),
#         A(f'{Tx("Append")}', href=f"/append/{bid}"),
#         A(f'{Tx("Download")} {Tx("DOCX file")}', href=f"/docx/{bid}"),
#         A(f'{Tx("Download")} {Tx("PDF file")}', href=f"/pdf/{bid}"),
#         A(f'{Tx("Download")} {Tx("TGZ file")}', href=f"/tgz/{bid}"),
#     ]

#     title = Tx("Information")
#     return (
#         Title(title),
#         components.header(request, title, book=book, menu=menu, status=book.status),
#         Main(*segments, cls="container"),
#     )


# @rt("/index/{bid:str}")
# def get(bid: str):
#     "List the indexed terms of the book."
#     book = books.get_book(bid)
#     items = []
#     for key, texts in sorted(book.indexed.items(), key=lambda tu: tu[0].lower()):
#         refs = []
#         for text in sorted(texts, key=lambda t: t.ordinal):
#             refs.append(
#                 Li(A(text.fulltitle, cls="secondary", href=f"/book/{bid}/{text.path}"))
#             )
#         items.append(Li(key, Small(Ul(*refs))))

#     title = Tx("Index")
#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(Ul(*items), cls="container"),
#     )


# @rt("/statuslist/{bid:str}")
# def get(bid: str):
#     "List each status and texts of the book in it."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     rows = [Tr(Th(Tx("Status"), Th(Tx("Texts"))))]
#     for status in constants.STATUSES:
#         texts = []
#         for t in book.all_texts:
#             if t.status == status:
#                 if texts:
#                     texts.append(Br())
#                 texts.append(A(t.heading, href=f"/book/{bid}/{t.path}"))
#         rows.append(
#             Tr(
#                 Td(
#                     components.blank(0.5, f"background-color: {status.color};"),
#                     components.blank(0.2),
#                     Tx(str(status)),
#                     valign="top",
#                 ),
#                 Td(*texts),
#             )
#         )

#     title = Tx("Status list")
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status),
#         Main(Table(*rows), cls="container"),
#     )


# @rt("/docx/{bid:str}")
# def get(bid: str):
#     "Download the DOCX for the whole book."
#     if not bid:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     return get_docx(bid)


# @rt("/docx/{bid:str}/{path:path}")
# def get(bid: str, path: str):
#     "Download the DOCX for a section or text in the book."
#     if not bid:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     return get_docx(bid, path)


# def get_docx(bid, path=""):
#     "Get the parameters for downloading the DOCX file."
#     book = books.get_book(bid)
#     if path:
#         item = book[path]
#     else:
#         item = None
#     settings = book.frontmatter.setdefault("docx", {})
#     title_page_metadata = settings.get("title_page_metadata", True)
#     page_break_level = settings.get("page_break_level", 1)
#     page_break_options = []
#     for value in range(0, 7):
#         if value == page_break_level:
#             page_break_options.append(Option(str(value), selected=True))
#         else:
#             page_break_options.append(Option(str(value)))
#     footnotes_location = settings.get(
#         "footnotes_location", constants.FOOTNOTES_EACH_TEXT
#     )
#     footnotes_options = []
#     for value in constants.FOOTNOTES_LOCATIONS:
#         if value == footnotes_location:
#             footnotes_options.append(
#                 Option(Tx(value.capitalize()), value=value, selected=True)
#             )
#         else:
#             footnotes_options.append(Option(Tx(value.capitalize()), value=value))
#     reference_font = settings.get("reference_font", constants.NORMAL)
#     reference_options = []
#     for value in constants.FONT_STYLES:
#         if value == reference_font:
#             reference_options.append(
#                 Option(Tx(value.capitalize()), value=value, selected=True)
#             )
#         else:
#             reference_options.append(Option(Tx(value.capitalize())))
#     indexed_font = settings.get("indexed_font", constants.NORMAL)
#     indexed_options = []
#     for value in constants.FONT_STYLES:
#         if value == indexed_font:
#             indexed_options.append(
#                 Option(Tx(value.capitalize()), value=value, selected=True)
#             )
#         else:
#             indexed_options.append(Option(Tx(value.capitalize()), value=value))
#     fields = []
#     if item is None:
#         fields.append(
#             Fieldset(
#                 Legend(Tx("Metadata on title page")),
#                 Label(
#                     Input(
#                         type="checkbox",
#                         name="title_page_metadata",
#                         role="switch",
#                         checked=bool(title_page_metadata),
#                     ),
#                     Tx("Display"),
#                 ),
#             )
#         )
#     else:
#         fields.append(Hidden(name="path", value=item.path))
#     fields.append(
#         Fieldset(
#             Legend(Tx("Page break level")),
#             Select(*page_break_options, name="page_break_level"),
#         )
#     )
#     if item is None:
#         fields.append(
#             Fieldset(
#                 Legend(Tx("Footnotes location")),
#                 Select(*footnotes_options, name="footnotes_location"),
#             )
#         )
#     else:
#         fields.append(Hidden(name="footnotes_location", value="after each text"))
#     fields.append(
#         Fieldset(
#             Legend(Tx("Reference font")),
#             Select(*reference_options, name="reference_font"),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Indexed font")), Select(*indexed_options, name="indexed_font")
#         )
#     )
#     fields.append(Button(f'{Tx("Download")} {Tx("DOCX file")}'))

#     if item is None:
#         title = book.title
#         status = book.status
#     else:
#         title = item.title
#         status = item.status

#     title = f'{Tx("Download")} {Tx("DOCX file")}: {title}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=status),
#         Main(
#             Form(*fields, action=f"/docx/{bid}", method="post"),
#             components.cancel_button(f"/book/{bid}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/docx/{bid:str}")
# def post(bid: str, form: dict):
#     "Actually download the DOCX file of the book."
#     book = books.get_book(bid)
#     path = form.get("path")
#     if path:
#         item = book[path]
#     else:
#         item = None
#     settings = book.frontmatter.setdefault("docx", {})
#     settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
#     settings["page_break_level"] = int(form["page_break_level"])
#     settings["footnotes_location"] = form["footnotes_location"]
#     settings["reference_font"] = form["reference_font"]
#     settings["indexed_font"] = form["indexed_font"]
#     if item is None:
#         book.write()
#         filename = book.title + ".docx"
#     else:
#         # Do not write out the book 'index.md'; the settings may be non-standard.
#         filename = item.title + ".docx"
#     creator = docx_creator.Creator(book, books.get_references(), item=item)
#     output = creator.create()

#     return Response(
#         content=output.getvalue(),
#         media_type=constants.DOCX_MIMETYPE,
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# @rt("/pdf/{bid:str}")
# def get(bid: str):
#     "Get the parameters for downloading PDF file of the whole book."
#     book = books.get_book(bid)
#     settings = book.frontmatter.setdefault("pdf", {})
#     title_page_metadata = settings.get("title_page_metadata", True)
#     page_break_level = settings.get("page_break_level", 1)
#     page_break_options = []
#     for value in range(0, 7):
#         if value == page_break_level:
#             page_break_options.append(Option(str(value), selected=True))
#         else:
#             page_break_options.append(Option(str(value)))
#     contents_pages = settings.get("contents_pages", True)
#     contents_level = settings.get("contents_level", 1)
#     contents_level_options = []
#     for value in range(0, 7):
#         if value == contents_level:
#             contents_level_options.append(Option(str(value), selected=True))
#         else:
#             contents_level_options.append(Option(str(value)))

#     footnotes_location = settings.get(
#         "footnotes_location", constants.FOOTNOTES_EACH_TEXT
#     )
#     footnotes_options = []
#     for value in constants.FOOTNOTES_LOCATIONS:
#         if value == footnotes_location:
#             footnotes_options.append(
#                 Option(Tx(value.capitalize()), value=value, selected=True)
#             )
#         else:
#             footnotes_options.append(Option(Tx(value.capitalize()), value=value))

#     indexed_xref = settings.get("indexed_xref", constants.PDF_PAGE_NUMBER)
#     indexed_options = []
#     for value in constants.PDF_INDEXED_XREF_DISPLAY:
#         if value == indexed_xref:
#             indexed_options.append(
#                 Option(Tx(value.capitalize()), value=value, selected=True)
#             )
#         else:
#             indexed_options.append(Option(Tx(value.capitalize()), value=value))

#     fields = []
#     fields.append(
#         Fieldset(
#             Legend(Tx("Metadata on title page")),
#             Label(
#                 Input(
#                     type="checkbox",
#                     name="title_page_metadata",
#                     role="switch",
#                     checked=bool(title_page_metadata),
#                 ),
#                 Tx("Display"),
#             ),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Page break level")),
#             Select(*page_break_options, name="page_break_level"),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Contents pages")),
#             Label(
#                 Input(
#                     type="checkbox",
#                     name="contents_pages",
#                     role="switch",
#                     checked=bool(contents_pages),
#                 ),
#                 Tx("Display in output"),
#             ),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Contents level")),
#             Select(*contents_level_options, name="contents_level"),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Footnotes location")),
#             Select(*footnotes_options, name="footnotes_location"),
#         )
#     )
#     fields.append(
#         Fieldset(
#             Legend(Tx("Display of indexed term reference")),
#             Select(*indexed_options, name="indexed_xref"),
#         )
#     )

#     title = f'{Tx("Download")} {Tx("PDF file")}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status),
#         Main(
#             Form(
#                 *fields,
#                 Button(f'{Tx("Download")} {Tx("PDF file")}'),
#                 action=f"/pdf/{bid}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{bid}"),
#             cls="container",
#         ),
#     )


# @rt("/pdf/{bid:str}")
# def post(bid: str, form: dict):
#     "Actually download the PDF file of the book."
#     book = books.get_book(bid)
#     settings = book.frontmatter.setdefault("pdf", {})
#     settings["title_page_metadata"] = bool(form.get("title_page_metadata", False))
#     settings["page_break_level"] = form["page_break_level"]
#     settings["contents_pages"] = form["contents_pages"]
#     settings["contents_level"] = form["contents_level"]
#     settings["footnotes_location"] = form["footnotes_location"]
#     settings["indexed_xref"] = form["indexed_xref"]
#     book.write()
#     filename = book.title + ".pdf"
#     creator = pdf_creator.Creator(book, books.get_references())
#     output = creator.create()

#     return Response(
#         content=output.getvalue(),
#         media_type=constants.PDF_MIMETYPE,
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# @rt("/tgz/{bid:str}")
# def get(bid: str):
#     "Download a gzipped tar file of the book."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     filename = f"mdbook_{book.bid}_{utils.timestr(safe=True)}.tgz"
#     output = book.get_tgzfile()

#     return Response(
#         content=output.getvalue(),
#         media_type=constants.GZIP_MIMETYPE,
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# @rt("/state/{bid:str}")
# def get(bid: str):
#     "Return JSON for complete state of this book."
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#     else:
#         book = books.get_book(bid)
#     result = dict(
#         software=constants.SOFTWARE,
#         version=constants.__version__,
#         now=utils.timestr(localtime=False, display=False),
#     )
#     result.update(book.state)

#     return result


# @rt("/system")
# def get(request):
#     "Display system information."
#     if not request.session.get("auth"):
#         raise NotAllowed

#     title = Tx("System")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Table(
#                 Tr(Td(Tx("User")), Td(request.session.get("auth") or "-")),
#                 Tr(
#                     Td(Tx("Memory usage")),
#                     Td(utils.thousands(psutil.Process().memory_info().rss), " bytes"),
#                 ),
#                 Tr(
#                     Td(A(constants.SOFTWARE, href="https://github.com/pekrau/mdbook")),
#                     Td(constants.__version__),
#                 ),
#                 Tr(
#                     Td(A("Python", href="https://www.python.org/")),
#                     Td(
#                         f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
#                     ),
#                 ),
#                 Tr(
#                     Td(A("fastHTML", href="https://fastht.ml/")),
#                     Td(fasthtml.__version__),
#                 ),
#                 Tr(
#                     Td(A("Marko", href="https://marko-py.readthedocs.io/")),
#                     Td(marko.__version__),
#                 ),
#                 Tr(
#                     Td(
#                         A(
#                             "python-docx",
#                             href="https://python-docx.readthedocs.io/en/latest/",
#                         )
#                     ),
#                     Td(docx_creator.docx.__version__),
#                 ),
#                 Tr(
#                     Td(A("fpdf2", href="https://py-pdf.github.io/fpdf2/")),
#                     Td(pdf_creator.fpdf.__version__),
#                 ),
#                 Tr(
#                     Td(A("PyYAML", href="https://pypi.org/project/PyYAML/")),
#                     Td(yaml.__version__),
#                 ),
#                 Tr(
#                     Td(
#                         A("bibtexparser", href="https://pypi.org/project/bibtexparser/")
#                     ),
#                     Td(bibtexparser.__version__),
#                 ),
#             ),
#             cls="container",
#         ),
#     )


# @rt("/tgz")
# def get():
#     "Download a gzipped tar file of all books."
#     filename = f"mdbook_{utils.timestr(safe=True)}.tgz"
#     return Response(
#         content=utils.get_tgzfile(Path(os.environ["MDBOOK_DIR"])).getvalue(),
#         media_type=constants.GZIP_MIMETYPE,
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# @rt("/state")
# def get():
#     "Return JSON for the overall state of this site."
#     return books.get_state()


# @rt("/differences")
# def get():
#     "Compare this local site with the update site."
#     try:
#         remote = utils.get_state_remote()
#     except ValueError as message:
#         raise Error(message, HTTP.INTERNAL_SERVER_ERROR)
#     state = books.get_state()
#     rows = []
#     here_books = state["books"].copy()
#     for bid, rbook in remote["books"].items():
#         rurl = os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{bid}"
#         lbook = here_books.pop(bid, {})
#         title = lbook.get("title") or rbook.get("title")
#         if lbook:
#             if lbook["digest"] == rbook["digest"]:
#                 action = Tx("Identical")
#             else:
#                 action = A(Tx("Differences"), href=f"/differences/{bid}", role="button")
#             rows.append(
#                 Tr(
#                     Th(Strong(title), scope="row"),
#                     Td(
#                         A(rurl, href=rurl),
#                         Br(),
#                         utils.tolocaltime(rbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(rbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td(
#                         A(bid, href=f"/book/{bid}"),
#                         Br(),
#                         utils.tolocaltime(lbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(lbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td(action),
#                 ),
#             )
#         else:
#             rows.append(
#                 Tr(
#                     Th(Strong(title), scope="row"),
#                     Td(
#                         A(rurl, href=rurl),
#                         Br(),
#                         utils.tolocaltime(rbook["modified"]),
#                         Br(),
#                         f'{utils.thousands(rbook["sum_characters"])} {Tx("characters")}',
#                     ),
#                     Td("-"),
#                     Td(
#                         Form(
#                             Button(Tx("Update here"), type="submit"),
#                             method="post",
#                             action=f"/pull/{bid}",
#                         )
#                     ),
#                 )
#             )
#     for bid, lbook in here_books.items():
#         rows.append(
#             Tr(
#                 Th(Strong(lbook.get("title") or rbook.get("title")), scope="row"),
#                 Td("-"),
#                 Td(
#                     A(bid, href=f"/book/{bid}"),
#                     Br(),
#                     utils.tolocaltime(lbook["modified"]),
#                     Br(),
#                     f'{utils.thousands(lbook["sum_characters"])} {Tx("characters")}',
#                 ),
#                 Td(A(Tx("Differences"), href=f"/differences/{bid}", role="button")),
#             ),
#         )

#     title = Tx("Differences")
#     return (
#         Title(title),
#         components.header(request, title),
#         Main(
#             Table(
#                 Thead(
#                     Tr(
#                         Th(Tx("Book")),
#                         Th(os.environ["MDBOOK_UPDATE_SITE"], scope="col"),
#                         Th(Tx("Here"), scope="col"),
#                         Th(scope="col"),
#                     ),
#                 ),
#                 Tbody(*rows),
#             ),
#             cls="container",
#         ),
#     )


# @rt("/differences/{bid:str}")
# def get(bid: str):
#     "Compare this local book with the update site book. One of them may not exist."
#     if not bid:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     try:
#         remote = utils.get_state_remote(bid)
#     except ValueError as message:
#         raise Error(message, HTTP.INTERNAL_SERVER_ERROR)
#     if bid == constants.REFERENCES:
#         book = books.get_references()
#         here = book.state
#     else:
#         try:
#             book = books.get_book(bid)
#             here = book.state
#         except Error:
#             here = {}
#     rurl = os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{bid}"
#     lurl = f"/book/{bid}"

#     rows, rflag, lflag = items_diffs(
#         remote.get("items", []), rurl, here.get("items", []), lurl
#     )

#     # The book 'index.md' files may differ, if they exist.
#     if remote and here:
#         row, rf, lf = item_diff(
#             remote,
#             os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{bid}",
#             here,
#             f"/book/{bid}",
#         )
#         if row:
#             rows.insert(0, row)
#             rflag += rf
#             lflag += lf

#     title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
#     if not rows:
#         if not remote:
#             segments = (
#                 H4(f'{Tx("Not present in")} {os.environ["MDBOOK_UPDATE_SITE"]}'),
#                 Form(
#                     Button(f'{Tx("Update")} {os.environ["MDBOOK_UPDATE_SITE"]}'),
#                     action=f"/push/{bid}",
#                     method="post",
#                 ),
#             )
#         elif not here:
#             segments = (
#                 H4(Tx("Not present here")),
#                 Form(
#                     Button(Tx("Update here")),
#                     action=f"/pull/{bid}",
#                     method="post",
#                 ),
#             )
#         else:
#             segments = (
#                 H4(Tx("Identical")),
#                 Div(
#                     Div(Strong(A(rurl, href=rurl))),
#                     Div(Strong(A(bid, href=lurl))),
#                     cls="grid",
#                 ),
#             )

#         return (
#             Title(title),
#             components.header(request, title, book=book),
#             Main(*segments, cls="container"),
#         )

#     rows.append(
#         Tr(
#             Td(),
#             Td(
#                 Form(
#                     Button(
#                         f'{Tx("Update")} {os.environ["MDBOOK_UPDATE_SITE"]}',
#                         cls=None if rflag else "outline",
#                     ),
#                     action=f"/push/{bid}",
#                     method="post",
#                 )
#             ),
#             Td(
#                 Form(
#                     Button(Tx("Update here"), cls=None if lflag else "outline"),
#                     action=f"/pull/{bid}",
#                     method="post",
#                 ),
#                 colspan=3,
#             ),
#         )
#     )

#     title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(
#             Table(
#                 Thead(
#                     Tr(
#                         Th(),
#                         Th(A(rurl, href=rurl), colspan=1, scope="col"),
#                         Th(A(bid, href=lurl), colspan=3, scope="col"),
#                     ),
#                     Tr(
#                         Th(Tx("Title"), scope="col"),
#                         Th(),
#                         Th(Tx("Age"), scope="col"),
#                         Th(Tx("Size"), scope="col"),
#                         Th(),
#                     ),
#                 ),
#                 Tbody(*rows),
#             ),
#             cls="container",
#         ),
#     )


# def items_diffs(ritems, rurl, litems, lurl):
#     """Return list of rows and flags specifying differences between
#     remote and local items.
#     """
#     result = []
#     rflag = 0
#     lflag = 0
#     for ritem in ritems:
#         riurl = f'{rurl}/{ritem["name"]}'
#         for pos, litem in enumerate(list(litems)):
#             if litem["title"] != ritem["title"]:
#                 continue
#             liurl = f'{lurl}/{litem["name"]}'
#             row, rf, lf = item_diff(ritem, riurl, litem, liurl)
#             rflag += rf
#             lflag += lf
#             if row:
#                 result.append(row)
#             litems.pop(pos)
#             try:
#                 rows, rf, lf = items_diffs(ritem["items"], riurl, litem["items"], liurl)
#                 rflag += rf
#                 lflag += lf
#                 result.extend(rows)
#             except KeyError as message:
#                 pass
#             break
#         else:
#             row, rf, lf = item_diff(ritem, riurl, None, None)
#             rflag += rf
#             lflag += lf
#             result.append(row)
#     for litem in litems:
#         row, rf, lf = item_diff(None, None, litem, f'{lurl}/{litem["name"]}')
#         rflag += rf
#         lflag += lf
#         result.append(row)
#     return result, rflag, lflag


# def item_diff(ritem, riurl, litem, liurl):
#     "Return row and update flags specifying differences between the items."
#     if ritem is None:
#         return (
#             Tr(
#                 Td(Strong(litem["title"])),
#                 Td("-"),
#                 Td("-"),
#                 Td("-"),
#                 Td(A(liurl, href=liurl)),
#             ),
#             1,
#             0,
#         )
#     elif litem is None:
#         return (
#             Tr(
#                 Td(Strong(ritem["title"])),
#                 Td(A(riurl, href=riurl)),
#                 Td("-"),
#                 Td("-"),
#                 Td("-"),
#             ),
#             0,
#             1,
#         )
#     if litem["digest"] == ritem["digest"]:
#         return None, 0, 0
#     if litem["modified"] < ritem["modified"]:
#         age = "Older"
#         rflag = 0
#         lflag = 1
#     elif litem["modified"] > ritem["modified"]:
#         age = "Newer"
#         rflag = 1
#         lflag = 0
#     else:
#         age = "Same"
#         rflag = 0
#         lflag = 0
#     if litem["n_characters"] < ritem["n_characters"]:
#         size = "Smaller"
#     elif litem["n_characters"] > ritem["n_characters"]:
#         size = "Larger"
#     else:
#         size = "Same"
#     return (
#         Tr(
#             Td(Strong(ritem["title"])),
#             Td(A(riurl, href=riurl)),
#             Td(Tx(age)),
#             Td(Tx(size)),
#             Td(A(liurl, href=liurl)),
#         ),
#         rflag,
#         lflag,
#     )


# @rt("/pull/{bid:str}")
# def post(bid: str):
#     "Update book at this site by downloading it from the remote site."
#     if not bid:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)

#     url = os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + f"/tgz/{bid}"
#     dirpath = Path(os.environ["MDBOOK_DIR"]) / bid
#     headers = dict(apikey=os.environ["MDBOOK_UPDATE_APIKEY"])

#     response = requests.get(url, headers=headers)

#     if response.status_code != HTTP.OK:
#         raise Error(f"remote error: {response.content}", HTTP.BAD_REQUEST)
#     if response.headers["Content-Type"] != constants.GZIP_MIMETYPE:
#         raise Error("invalid file type from remote", HTTP.BAD_REQUEST)
#     content = response.content
#     if not content:
#         raise Error("empty TGZ file from remote", HTTP.BAD_REQUEST)

#     # Temporarily save old contents.
#     if dirpath.exists():
#         saved_dirpath = Path(os.environ["MDBOOK_DIR"]) / "_saved"
#         dirpath.replace(saved_dirpath)
#     else:
#         saved_dirpath = None
#     try:
#         utils.unpack_tgzfile(dirpath, content, references=bid == constants.REFERENCES)
#     except ValueError as message:
#         # If failure, reinstate saved contents.
#         if saved_dirpath:
#             saved_dirpath.replace(dirpath)
#         raise Error(f"error reading TGZ file from remote: {message}", HTTP.BAD_REQUEST)
#     else:
#         # Remove saved contents after new was successful unpacked.
#         if saved_dirpath:
#             shutil.rmtree(saved_dirpath)

#     if bid == constants.REFERENCES:
#         books.get_references(refresh=True)
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)
#     else:
#         books.get_book(bid, refresh=True)
#         return RedirectResponse(f"/book/{bid}", status_code=HTTP.SEE_OTHER)


# @rt("/push/{bid:str}")
# def post(bid: str):
#     "Update book at the remote site by uploading it from this site."
#     if not bid:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     url = os.environ["MDBOOK_UPDATE_SITE"].rstrip("/") + f"/receive/{bid}"
#     dirpath = Path(os.environ["MDBOOK_DIR"]) / bid
#     tgzfile = utils.get_tgzfile(dirpath)
#     tgzfile.seek(0)
#     headers = dict(apikey=os.environ["MDBOOK_UPDATE_APIKEY"])
#     response = requests.post(
#         url,
#         headers=headers,
#         files=dict(tgzfile=("tgzfile", tgzfile, constants.GZIP_MIMETYPE)),
#     )
#     if response.status_code != HTTP.OK:
#         error(f"remote did not accept push: {response.content}", HTTP.BAD_REQUEST)
#     return RedirectResponse("/", status_code=HTTP.SEE_OTHER)


# @rt("/receive/{bid:str}")
# async def post(bid: str, tgzfile: UploadFile = None):
#     "Update book at this site by another site uploading it."
#     if not bid:
#         raise Error("book bid may not be empty", HTTP.BAD_REQUEST)
#     if bid.startswith("_"):
#         raise Error("book bid may not start with an underscore '_'", HTTP.BAD_REQUEST)

#     content = await tgzfile.read()
#     if not content:
#         raise Error("no content in TGZ file", HTTP.BAD_REQUEST)

#     dirpath = Path(os.environ["MDBOOK_DIR"]) / bid
#     if dirpath.exists():
#         # Temporarily save old contents.
#         saved_dirpath = Path(os.environ["MDBOOK_DIR"]) / "_saved"
#         dirpath.rename(saved_dirpath)
#     else:
#         saved_dirpath = None
#     try:
#         utils.unpack_tgzfile(dirpath, content)
#         if saved_dirpath:
#             shutil.rmtree(saved_dirpath)
#     except ValueError as message:
#         if saved_dirpath:
#             saved_dirpath.rename(dirpath)
#         raise Error(f"error reading TGZ file: {message}", HTTP.BAD_REQUEST)

#     if bid == constants.REFERENCES:
#         books.get_references(refresh=True)
#     else:
#         books.get_book(bid, refresh=True)
#     return "success"


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
books.read_books()

serve()
