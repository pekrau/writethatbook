"""WriteThatBook
Write books in a web-based app using Markdown files, allowing
references and indexing, creating DOCX or PDF.
"""

from icecream import ic

import io
from http import HTTPStatus as HTTP
import os
from pathlib import Path
import tarfile

from fasthtml.common import *

import auth
import books, book_app
import components
import constants
import edit_app
from errors import *
import meta_app
import move_app
import users, user_app
import utils
from utils import Tx


if "WRITETHATBOOK_DIR" not in os.environ:
    raise ValueError("env var WRITETHATBOOK_DIR not defined: cannot execute")


app, rt = utils.get_fast_app(
    routes=[
        Mount("/book", book_app.app),
        Mount("/edit", edit_app.app),
        Mount("/move", move_app.app),
        Mount("/user", user_app.app),
        Mount("/meta", meta_app.app),
    ],
)


@rt("/")
def get(request):
    "Home page; list of books."
    auth.allow_anyone(request)
    hrows = Tr(
        Th(Tx("Title")),
        Th(Tx("Type")),
        Th(Tx("Status")),
        Th(Tx("Characters")),
        Th(Tx("Owner")),
        Th(Tx("Modified")),
    )
    rows = []
    for book in books.get_books(request):
        if not auth.authorized(request, *auth.book_view_rules, book=book):
            continue
        rows.append(
            Tr(
                Td(A(book.title, href=f"/book/{book.id}")),
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
    menu = [A(Tx("References"), href="/refs")]
    user = auth.logged_in(request)
    if user:
        menu.append(A(Tx("Create or upload book"), href="/book"))
        menu.append(A(f'{Tx("User")} {user}', href=f"/user/view/{user.id}"))
    if auth.is_admin(request):
        menu.append(A(Tx("All users"), href="/user/list"))
        if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
            menu.append(A(Tx("Differences"), href="/differences"))
        menu.append(A(f'{Tx("Download")} {Tx("dump")}', href="/dump"))
        menu.append(A(Tx("State (JSON)"), href="/meta/state"))
        menu.append(A(Tx("System"), href="/meta/system"))
    menu.append(A(Tx("Software"), href="/meta/software"))

    title = Tx("Books")
    return (
        Title(title),
        components.header(request, title, menu=menu),
        Main(Table(Thead(*hrows), Tbody(*rows)), cls="container"),
    )


@rt("/ping")
def get(request):
    "Health check."
    auth.allow_anyone(request)
    return f"Hello, {request.scope.get('current_user') or 'anonymous'}!"


@rt("/dump")
def get(request):
    "Download a gzipped tar file of all data."
    auth.allow_admin(request)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tgzfile:
        for path in Path(os.environ["WRITETHATBOOK_DIR"]).iterdir():
            tgzfile.add(path, arcname=path.name, recursive=True)
    filename = f"writethatbook_{utils.timestr(safe=True)}.tgz"

    return Response(
        content=buffer.getvalue(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
#                 Strong(ref["name"], style=f"color: {constants.REFS_COLOR};"),
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
#                 symbol, url = constants.REFS_LINKS["isbn"]
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
#             symbol, url = constants.REFS_LINKS["doi"]
#             url = url.format(value=ref["doi"])
#             if links:
#                 links.append(", ")
#             links.append(A(f'{symbol}:{ref["doi"]}', href=url.format(value=ref["doi"])))
#         if ref.get("pmid"):
#             symbol, url = constants.REFS_LINKS["pmid"]
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
#                         href=f"/book/{book.id}/{text.path}",
#                     )
#                 )
#         if xrefs:
#             parts.append(Small(Br(), *xrefs))

#         items.append(P(*parts, id=ref["name"]))

#     menu = [A(Tx("Keywords"), href="/references/keywords")]
#     menu.extend(
#         [
#             A(Tx(f'{Tx("Add reference")}: {Tx(type)}'), href=f"/reference/add/{type}")
#             for type in constants.REFS_TYPES
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
#     if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
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

#     menu = [components.refs_link()]

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
#         Path(os.environ["WRITETHATBOOK_DIR"]) / constants.REFSS,
#         await tgzfile.read(),
#         references=True,
#     )
#     books.get_references(reread=True)

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
#     books.get_references(reread=True)

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

#     # Reread the cache.
#     references = books.get_references(reread=True)

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
#         url = constants.REFS_LINKS["isbn"][1].format(value=ref["isbn"])
#         rows.append(Tr(Td("ISBN"), Td(A(ref["isbn"], href=url))))
#     if ref.get("pmid"):
#         url = constants.REFS_LINKS["pmid"][1].format(value=ref["pmid"])
#         rows.append(Tr(Td("PubMed"), Td(A(ref["pmid"], href=url))))
#     if ref.get("doi"):
#         url = constants.REFS_LINKS["doi"][1].format(value=ref["doi"])
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
#                     href=f"/book/{book.id}/{text.path}",
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
#         components.refs_link(),
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
#     books.get_references(reread=True)

#     return RedirectResponse(f"/reference/{refid}", status_code=HTTP.SEE_OTHER)




# @rt("/copy/{id:str}")
# def get(auth, id: str):
#     "Make a copy of the book."
#     book = books.get_book(id)
#     new = book.copy(owner=auth)

#     return RedirectResponse(f"/book/{new.id}", status_code=HTTP.SEE_OTHER)


# @rt("/delete/{id:str}")
# def get(id: str):
#     "Confirm deleting book."
#     book = books.get_book(id)

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
#             Form(Button(Tx("Confirm")), action=f"/delete/{id}", method="post"),
#             components.cancel_button(f"/book/{id}"),
#             cls="container",
#         ),
#     )


# @rt("/delete/{id:str}")
# def post(id: str):
#     "Actually delete the book, even if it contains items."
#     book = books.get_book(id)
#     book.delete(force=True)

#     return RedirectResponse("/", status_code=HTTP.SEE_OTHER)


# @rt("/search/{id:str}")
# def post(id: str, form: dict):
#     "Actually search the book for a given term."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
#     term = form.get("term")
#     if term:
#         items = [
#             Li(A(i.fulltitle, href=f"/book/{id}/{i.path}"))
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
#     if id != constants.REFSS:
#         menu.append(components.refs_link())

#     title = f'{Tx("Search")} {Tx("book")}'
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=book.status, menu=menu),
#         Main(
#             components.search_form(f"/search/{id}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/recent/{id:str}")
# def get(id: str):
#     "Display the most recently modified items in the book."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)

#     items = book.all_items
#     items.sort(key=lambda i: i.modified, reverse=True)
#     items = items[: constants.MAX_RECENT]

#     menu = [components.index_link(book)]

#     if id == constants.REFSS:
#         menu.append(components.refs_link())
#         rows = [
#             Tr(
#                 Td(A(i["name"], href=f"/reference/{i.path}"), ": ", i.fulltitle),
#                 Td(i.modified),
#             )
#             for i in items
#         ]
#     else:
#         rows = [
#             Tr(Td(A(i.fulltitle, href=f"/book/{id}/{i.path}")), Td(i.modified))
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


# @rt("/append/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Append to the content of an item."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
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
#                 action=f"/append/{id}/{path}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{id}/{path}"),  # This works for all.
#             cls="container",
#         ),
#     )


# @rt("/append/{id:str}/{path:path}")
# def post(id: str, path: str, content: str):
#     "Actually append to the content of an item."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
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

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/append/{id}/{path}", status_code=HTTP.SEE_OTHER)


# @rt("/search/{id:str}/{path:path}")
# def post(id: str, path: str, form: dict):
#     "Actually search the item (text or section)  for a given term."
#     book = books.get_book(id)
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
#             components.search_form(f"/search/{id}/{path}", term=term),
#             result,
#             cls="container",
#         ),
#     )


# @rt("/copy/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Make a copy of the item (text or section)."
#     path = books.get_book(id)[path].copy()
#     return RedirectResponse(f"/book/{id}/{path}", status_code=HTTP.SEE_OTHER)


# @rt("/delete/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Confirm delete of the text or section; section must be empty."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
#     item = book[path]
#     if len(item.items) != 0 or item.content:
#         segments = [P(Strong(Tx("Note: all contents will be lost!")))]
#     else:
#         segments = []

#     if id == constants.REFSS:
#         title = f"{Tx('Delete')} {Tx('reference')} '{item['name']}'?"
#     else:
#         title = f"{Tx('Delete')} {Tx(item.type)} '{item.fulltitle}'?"

#     return (
#         Title(title),
#         components.header(request, title, book=book, status=item.status),
#         Main(
#             H3(Tx("Delete"), "?"),
#             *segments,
#             Form(Button(Tx("Confirm")), action=f"/delete/{id}/{path}", method="post"),
#             components.cancel_button(f"/book/{id}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/delete/{id:str}/{path:path}")
# def post(id: str, path: str):
#     "Delete the text or section."
#     if id == constants.REFSS:
#         book = books.get_references()
#     else:
#         book = books.get_book(id)
#     item = book[path]
#     item.delete(force=True)

#     if id == constants.REFSS:
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)
#     else:
#         return RedirectResponse(f"/book/{id}", status_code=HTTP.SEE_OTHER)


# @rt("/to_section/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Convert to section containing a text with this text."
#     book = books.get_book(id)
#     text = book[path]
#     assert text.is_text

#     title = f"{Tx('Convert to section')}: '{text.fulltitle}'"
#     return (
#         Title(title),
#         components.header(request, title, book=book, status=text.status),
#         Main(
#             Form(
#                 Button(Tx("Convert")), action=f"/to_section/{id}/{path}", method="post"
#             ),
#             components.cancel_button(f"/book/{id}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/to_section/{id:str}/{path:path}")
# def post(id: str, path: str):
#     "Actually convert to section containing a text with this text."
#     book = books.get_book(id)
#     text = book[path]
#     assert text.is_text
#     section = text.to_section()

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/book/{id}/{section.path}", status_code=HTTP.SEE_OTHER)


# @rt("/text/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Create a new text in the section."
#     book = books.get_book(id)
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
#                 action=f"/text/{id}/{path}",
#                 method="post",
#             ),
#             components.cancel_button(f"/book/{id}/{path}"),
#             cls="container",
#         ),
#     )


# @rt("/text/{id:str}/{path:path}")
# def post(id: str, path: str, title: str = None):
#     "Actually create a new text in the section."
#     book = books.get_book(id)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_text(title, parent=parent)

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{id}/{new.path}", status_code=HTTP.SEE_OTHER)


# @rt("/section/{id:str}/{path:path}")
# def get(id: str, path: str):
#     "Create a new section in the section."
#     book = books.get_book(id)
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
#                 action=f"/section/{id}/{path}",
#                 method="post",
#             ),
#             cls="container",
#         ),
#     )


# @rt("/section/{id:str}/{path:path}")
# def post(id: str, path: str, title: str = None):
#     "Actually create a new section in the section."
#     book = books.get_book(id)
#     if path == "":
#         parent = None
#     else:
#         parent = book[path]
#         assert parent.is_section
#     new = book.create_section(title, parent=parent)

#     # Reread the book, ensuring everything is up to date.
#     book.write()
#     book.read()

#     return RedirectResponse(f"/edit/{id}/{new.path}", status_code=HTTP.SEE_OTHER)


# @rt("/index/{id:str}")
# def get(id: str):
#     "List the indexed terms of the book."
#     book = books.get_book(id)
#     items = []
#     for key, texts in sorted(book.indexed.items(), key=lambda tu: tu[0].lower()):
#         refs = []
#         for text in sorted(texts, key=lambda t: t.ordinal):
#             refs.append(
#                 Li(A(text.fulltitle, cls="secondary", href=f"/book/{id}/{text.path}"))
#             )
#         items.append(Li(key, Small(Ul(*refs))))

#     title = Tx("Index")
#     return (
#         Title(title),
#         components.header(request, title, book=book),
#         Main(Ul(*items), cls="container"),
#     )




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
#     for id, rbook in remote["books"].items():
#         rurl = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}"
#         lbook = here_books.pop(id, {})
#         title = lbook.get("title") or rbook.get("title")
#         if lbook:
#             if lbook["digest"] == rbook["digest"]:
#                 action = Tx("Identical")
#             else:
#                 action = A(Tx("Differences"), href=f"/differences/{id}", role="button")
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
#                         A(id, href=f"/book/{id}"),
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
#                             action=f"/pull/{id}",
#                         )
#                     ),
#                 )
#             )
#     for id, lbook in here_books.items():
#         rows.append(
#             Tr(
#                 Th(Strong(lbook.get("title") or rbook.get("title")), scope="row"),
#                 Td("-"),
#                 Td(
#                     A(id, href=f"/book/{id}"),
#                     Br(),
#                     utils.tolocaltime(lbook["modified"]),
#                     Br(),
#                     f'{utils.thousands(lbook["sum_characters"])} {Tx("characters")}',
#                 ),
#                 Td(A(Tx("Differences"), href=f"/differences/{id}", role="button")),
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
#                         Th(os.environ["WRITETHATBOOK_UPDATE_SITE"], scope="col"),
#                         Th(Tx("Here"), scope="col"),
#                         Th(scope="col"),
#                     ),
#                 ),
#                 Tbody(*rows),
#             ),
#             cls="container",
#         ),
#     )


# @rt("/differences/{id:str}")
# def get(id: str):
#     "Compare this local book with the update site book. One of them may not exist."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     try:
#         remote = utils.get_state_remote(id)
#     except ValueError as message:
#         raise Error(message, HTTP.INTERNAL_SERVER_ERROR)
#     if id == constants.REFSS:
#         book = books.get_references()
#         here = book.state
#     else:
#         try:
#             book = books.get_book(id)
#             here = book.state
#         except Error:
#             here = {}
#     rurl = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}"
#     lurl = f"/book/{id}"

#     rows, rflag, lflag = items_diffs(
#         remote.get("items", []), rurl, here.get("items", []), lurl
#     )

#     # The book 'index.md' files may differ, if they exist.
#     if remote and here:
#         row, rf, lf = item_diff(
#             remote,
#             os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/book/{id}",
#             here,
#             f"/book/{id}",
#         )
#         if row:
#             rows.insert(0, row)
#             rflag += rf
#             lflag += lf

#     title = f"{Tx('Differences in')} {Tx('book')} '{book.title}'"
#     if not rows:
#         if not remote:
#             segments = (
#                 H4(f'{Tx("Not present in")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}'),
#                 Form(
#                     Button(f'{Tx("Update")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}'),
#                     action=f"/push/{id}",
#                     method="post",
#                 ),
#             )
#         elif not here:
#             segments = (
#                 H4(Tx("Not present here")),
#                 Form(
#                     Button(Tx("Update here")),
#                     action=f"/pull/{id}",
#                     method="post",
#                 ),
#             )
#         else:
#             segments = (
#                 H4(Tx("Identical")),
#                 Div(
#                     Div(Strong(A(rurl, href=rurl))),
#                     Div(Strong(A(id, href=lurl))),
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
#                         f'{Tx("Update")} {os.environ["WRITETHATBOOK_UPDATE_SITE"]}',
#                         cls=None if rflag else "outline",
#                     ),
#                     action=f"/push/{id}",
#                     method="post",
#                 )
#             ),
#             Td(
#                 Form(
#                     Button(Tx("Update here"), cls=None if lflag else "outline"),
#                     action=f"/pull/{id}",
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
#                         Th(A(id, href=lurl), colspan=3, scope="col"),
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


# @rt("/pull/{id:str}")
# def post(id: str):
#     "Update book at this site by downloading it from the remote site."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)

#     url = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/tgz/{id}"
#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     headers = dict(apikey=os.environ["WRITETHATBOOK_UPDATE_APIKEY"])

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
#         saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
#         dirpath.replace(saved_dirpath)
#     else:
#         saved_dirpath = None
#     try:
#         utils.unpack_tgzfile(dirpath, content, references=id == constants.REFSS)
#     except ValueError as message:
#         # If failure, reinstate saved contents.
#         if saved_dirpath:
#             saved_dirpath.replace(dirpath)
#         raise Error(f"error reading TGZ file from remote: {message}", HTTP.BAD_REQUEST)
#     else:
#         # Remove saved contents after new was successful unpacked.
#         if saved_dirpath:
#             shutil.rmtree(saved_dirpath)

#     if id == constants.REFSS:
#         books.get_references(reread=True)
#         return RedirectResponse("/references", status_code=HTTP.SEE_OTHER)
#     else:
#         books.get_book(id, reread=True)
#         return RedirectResponse(f"/book/{id}", status_code=HTTP.SEE_OTHER)


# @rt("/push/{id:str}")
# def post(id: str):
#     "Update book at the remote site by uploading it from this site."
#     if not id:
#         raise Error("no book id provided", HTTP.BAD_REQUEST)
#     url = os.environ["WRITETHATBOOK_UPDATE_SITE"].rstrip("/") + f"/receive/{id}"
#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     tgzfile = utils.get_tgzfile(dirpath)
#     tgzfile.seek(0)
#     headers = dict(apikey=os.environ["WRITETHATBOOK_UPDATE_APIKEY"])
#     response = requests.post(
#         url,
#         headers=headers,
#         files=dict(tgzfile=("tgzfile", tgzfile, constants.GZIP_MIMETYPE)),
#     )
#     if response.status_code != HTTP.OK:
#         error(f"remote did not accept push: {response.content}", HTTP.BAD_REQUEST)
#     return RedirectResponse("/", status_code=HTTP.SEE_OTHER)


# @rt("/receive/{id:str}")
# async def post(id: str, tgzfile: UploadFile = None):
#     "Update book at this site by another site uploading it."
#     if not id:
#         raise Error("book id may not be empty", HTTP.BAD_REQUEST)
#     if id.startswith("_"):
#         raise Error("book id may not start with an underscore '_'", HTTP.BAD_REQUEST)

#     content = await tgzfile.read()
#     if not content:
#         raise Error("no content in TGZ file", HTTP.BAD_REQUEST)

#     dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / id
#     if dirpath.exists():
#         # Temporarily save old contents.
#         saved_dirpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "_saved"
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

#     if id == constants.REFS:
#         books.get_references(reread=True)
#     else:
#         books.get_book(id, reread=True)
#     return "success"


# Initialize the users database.
users.initialize()

# Read in all books and references into memory.
books.read_books()

serve()
