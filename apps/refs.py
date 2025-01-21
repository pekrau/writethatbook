"References list, view and edit pages."

import io
import re
import string
import tarfile

import bibtexparser
from fasthtml.common import *
import latex_utf8

import auth
import books
from books import Text, get_refs
import components
import constants
import markdown
import utils
from utils import Tx


class RefConvertor(Convertor):
    regex = "[a-z-]+-[0-9]+[a-z]*"

    def convert(self, value: str) -> Text:
        return get_refs()[value]

    def to_string(self, value: Text) -> str:
        return value["id"]


register_url_convertor("Ref", RefConvertor())


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "List of references."
    auth.allow_anyone(request)

    refs = get_refs()
    items = []
    for ref in refs.items:
        parts = [
            Img(
                src="/clipboard.svg",
                title=Tx("Reference to clipboard"),
                style="cursor: pointer;",
                cls="white to_clipboard",
                data_clipboard_action="copy",
                data_clipboard_text=f"[@{ref['name']}]",
            ),
            components.blank(0.1),
            A(
                Strong(ref["name"], style=f"color: {constants.REFS_COLOR};"),
                href=f"/refs/{ref}",
            ),
            components.blank(0.2),
        ]
        parts.append(utils.full_title(ref))
        parts.append(Br())
        if ref.get("authors"):
            authors = [utils.short_name(a) for a in ref["authors"]]
            if len(authors) > constants.MAX_DISPLAY_AUTHORS:
                authors = (
                    authors[: constants.MAX_DISPLAY_AUTHORS - 1]
                    + ["..."]
                    + [authors[-1]]
                )
            parts.append("; ".join(authors))

        parts.append(Br())
        links = []
        if ref["type"] == constants.ARTICLE:
            if ref.get("journal"):
                value = ref["journal"]
                if value.startswith("[@"):
                    value = value[2:-1]
                    parts.append(" ")
                    parts.append(Tx("Part of"))
                    parts.append(" ")
                    parts.append(A(value, href=f"/refs/{utils.nameify(value)}"))
                else:
                    parts.append(I(ref["journal"]))
            if ref.get("volume"):
                parts.append(f' {ref["volume"]}')
            if ref.get("number"):
                parts.append(f' ({ref["number"]})')
            if ref.get("pages"):
                parts.append(f' {ref["pages"].replace("--", "-")}')
            if ref.get("year"):
                parts.append(f' ({ref["year"]})')
            if ref.get("edition_published"):
                parts.append(f' [{ref["edition_published"]}]')
        elif ref["type"] == constants.BOOK:
            if ref.get("publisher"):
                parts.append(f'{ref["publisher"]}')
            # Edition published later than original publication.
            if ref.get("edition_published"):
                parts.append(f' {ref["edition_published"]}')
                if ref.get("year"):
                    parts.append(f' [{ref["year"]}]')
            # Standard case; publication and edition same year.
            elif ref.get("year"):
                parts.append(f' {ref["year"]}')
            if ref.get("isbn"):
                symbol, url = constants.REFS_LINKS["isbn"]
                url = url.format(value=ref["isbn"])
                if links:
                    links.append(", ")
                links.append(
                    A(f'{symbol}:{ref["isbn"]}', href=url.format(value=ref["isbn"]))
                )
        elif ref["type"] == constants.LINK:
            if ref.get("publisher"):
                parts.append(f'{ref["publisher"]}')
            if ref.get("year"):
                parts.append(f' ({ref["year"]})')

        if ref.get("url"):
            parts.append(Br())
            parts.append(A(ref["url"], href=ref["url"]))
            if ref.get("accessed"):
                parts.append(f' (Accessed: {ref["accessed"]})')
        if ref.get("doi"):
            symbol, url = constants.REFS_LINKS["doi"]
            url = url.format(value=ref["doi"])
            if links:
                links.append(", ")
            links.append(A(f'{symbol}:{ref["doi"]}', href=url.format(value=ref["doi"])))
        if ref.get("pmid"):
            symbol, url = constants.REFS_LINKS["pmid"]
            url = url.format(value=ref["pmid"])
            if links:
                links.append(", ")
            links.append(
                A(f'{symbol}:{ref["pmid"]}', href=url.format(value=ref["pmid"]))
            )

        if links:
            parts.append(" ")
            parts.extend(links)

        xrefs = []
        for book in books.get_books(request):
            texts = book.refs.get(ref["id"], [])
            for text in sorted(texts, key=lambda t: t.ordinal):
                if xrefs:
                    xrefs.append(Br())
                xrefs.append(
                    A(
                        f"{book.title}: {text.fulltitle}",
                        cls="secondary",
                        href=f"/book/{book}/{text.path}",
                    )
                )
        if xrefs:
            parts.append(Small(Br(), *xrefs))

        items.append(P(*parts, id=ref["name"]))

    actions = []
    if auth.authorized(request, *auth.refs_add_rules, refs=refs):
        actions.extend(
            [
                (f'{Tx("Add reference")}: {Tx(type)}', f"/refs/add/{type}")
                for type in constants.REFS_TYPES
            ]
        )
        actions.extend(
            [
                (f'{Tx("Add reference(s)")}: BibTex', "/refs/bibtex"),
                (Tx("Upload TGZ file"), "/refs/upload"),
            ]
        )
    if auth.authorized(request, *auth.book_diff_rules, book=refs):
        actions.append(["Differences", f"/diff/{constants.REFS}"])

    title = f"{len(refs.items)}"
    return (
        Title(title),
        Script(src="/clipboard.min.js"),
        Script("new ClipboardJS('.to_clipboard');"),
        components.header(request, title, book=refs, actions=actions),
        Main(components.search_form("/refs/search"), *items, cls="container"),
        components.footer(request),
    )


@rt("/{ref:Ref}")
def get(request, ref: Text, position: int = None):
    "Display the reference."
    auth.allow_anyone(request)

    rows = [
        Tr(
            Td(Tx("Reference")),
            Td(
                f"{ref['name']}",
                components.blank(0.1),
                Img(
                    src="/clipboard.svg",
                    title=Tx("Reference to clipboard"),
                    style="cursor: pointer;",
                    cls="white to_clipboard",
                    data_clipboard_action="copy",
                    data_clipboard_text=f"[@{ref['name']}]",
                ),
            ),
        ),
        Tr(Td(Tx("Authors"), valign="top"), Td("; ".join(ref.get("authors") or []))),
    ]
    for key in [
        "title",
        "subtitle",
        "year",
        "edition_published",
        "date",
    ]:
        value = ref.get(key)
        if value:
            rows.append(
                Tr(Td((Tx(key.replace("_", " ")).title()), valign="top"), Td(value))
            )

    if ref.get("journal"):
        value = ref["journal"]
        if value.startswith("[@"):
            value = value[2:-1]
            rows.append(
                Tr(
                    Td(Tx("Part of"), valign="top"),
                    Td(Strong(A(value, href=f"/refs/{utils.nameify(value)}"))),
                )
            )
        else:
            rows.append(Tr(Td(Tx("Journal"), valign="top"), Td(value)))

    for key in [
        "volume",
        "number",
        "pages",
        "language",
        "publisher",
    ]:
        value = ref.get(key)
        if value:
            rows.append(
                Tr(Td((Tx(key.replace("_", " ")).title()), valign="top"), Td(value))
            )

    if ref.get("keywords"):
        rows.append(
            Tr(Td(Tx("Keywords"), valign="top"), Td("; ".join(ref["keywords"])))
        )
    if ref.get("issn"):
        rows.append(Tr(Td("ISSN"), Td(ref["issn"])))
    if ref.get("isbn"):
        url = constants.REFS_LINKS["isbn"][1].format(value=ref["isbn"])
        rows.append(Tr(Td("ISBN"), Td(A(ref["isbn"], href=url))))
    if ref.get("pmid"):
        url = constants.REFS_LINKS["pmid"][1].format(value=ref["pmid"])
        rows.append(Tr(Td("PubMed"), Td(A(ref["pmid"], href=url))))
    if ref.get("doi"):
        url = constants.REFS_LINKS["doi"][1].format(value=ref["doi"])
        rows.append(Tr(Td("DOI"), Td(A(ref["doi"], href=url))))
    if ref.get("url"):
        rows.append(Tr(Td("Url"), Td(A(ref["url"], href=ref["url"]))))
    xrefs = []
    for book in books.get_books(request):
        texts = book.refs.get(ref["id"], [])
        for text in sorted(texts, key=lambda t: t.ordinal):
            if xrefs:
                xrefs.append(Br())
            xrefs.append(
                A(
                    f"{book.title}: {text.fulltitle}",
                    href=f"/book/{book.id}/{text.path}",
                )
            )
    contains = []
    refvalue = f"[@{ref['name']}]"
    for r in get_refs():
        if r.get("journal") == refvalue:
            if contains:
                contains.append(Br())
            contains.append(A(r["name"], href=f"/refs/{r}"))
            contains.append(" ")
            contains.append(r.title)
    if contains:
        rows.append(Tr(Td(Tx("Contains")), Td(*contains)))

    rows.append(Tr(Td(Tx("Referenced by"), valign="top"), Td(*xrefs)))

    if auth.authorized(request, *auth.ref_edit_rules, ref=ref):
        actions = [
            ("Edit", f"/refs/edit/{ref['id']}"),
            ("Append", f"/refs/append/{ref['id']}"),
            ("Delete", f"/refs/delete/{ref['id']}"),
        ]

        kwargs = {"role": "button", "style": "width: 10em;"}
        buttons = [
            Div(A(Tx("Edit"), href=f"/refs/edit/{ref['id']}", **kwargs)),
            Div(A(Tx("Append"), href=f"/refs/append/{ref['id']}", **kwargs)),
            Div(),
            Div(),
        ]
    else:
        actions = []

    title = f"{ref['name']} ({Tx(ref['type'])})"
    html = markdown.to_html(get_refs(), ref.content)

    return (
        Title(title),
        Script(src="/clipboard.min.js"),
        Script("new ClipboardJS('.to_clipboard');"),
        components.header(
            request,
            title,
            book=get_refs(),
            status=ref.status,
            actions=actions,
        ),
        Main(
            Table(*rows),
            Div(NotStr(html), style="margin-top: 1em;"),
            Card(*buttons, cls="grid"),
            cls="container",
        ),
        components.footer(request, ref),
    )


@rt("/edit/{ref:Ref}")
def get(request, ref: Text):
    "Edit the reference."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)
    title = f"{Tx('Edit')} '{ref['name']}' ({Tx(ref['type'])})"
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                *get_ref_fields(ref=ref, type=ref["type"]),
                components.get_status_field(ref),
                components.save_button(),
                action=f"/refs/edit/{ref['id']}",
                method="post",
            ),
            components.cancel_button(f"/refs/{ref['id']}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/edit/{ref:Ref}")
def post(request, ref: Text, form: dict):
    "Actually edit the reference."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)
    try:
        ref.status = form.pop("status")
    except KeyError:
        pass
    get_ref_from_form(form, ref=ref)
    get_refs(reread=True)

    return components.redirect(f"/refs/{ref['id']}")


@rt("/append/{ref:Ref}")
def get(request, ref: Text):
    "Append to the content of the reference."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)

    title = f'{Tx("Append")} {ref["name"]}'
    return (
        Title(title),
        components.header(request, title, book=get_refs()),
        Main(
            Form(
                Textarea(name="content", rows=16, autofocus=True),
                components.save_button("Append"),
                action=f"/refs/append/{ref['id']}",
                method="post",
            ),
            components.cancel_button(f"/refs/{ref['id']}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/append/{ref:Ref}")
def post(request, ref: Text, content: str):
    "Actually append to the content of the reference."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)

    # Slot in appended content before footnotes, if any.
    lines = ref.content.split("\n")
    for pos, line in enumerate(lines):
        if line.startswith("[^"):
            lines.insert(pos - 1, content + "\n")
            break
    else:
        lines.append(content)
    ref.write(content="\n".join(lines))

    # Write out and reread the book, ensuring everything is up to date.
    refs = get_refs()
    refs.write()
    refs.read()

    return components.redirect(f"/refs/{ref['id']}")


@rt("/keywords")
def get(request):
    "List the keyword terms of the references."
    auth.allow_anyone(request)

    refs = get_refs()
    items = []
    for key, texts in sorted(refs.indexed.items(), key=lambda tu: tu[0].lower()):
        xrefs = []
        for text in sorted(texts, key=lambda t: t.ordinal):
            xrefs.append(
                Li(
                    A(
                        f'{text["name"]}: {text.fulltitle}',
                        cls="secondary",
                        href=f"/refs/{text.path}",
                    )
                )
            )
        items.append(Li(key, Small(Ul(*xrefs))))

    title = Tx("Keywords")
    return (
        Title(title),
        components.header(request, title, book=refs),
        Main(Ul(*items), cls="container"),
        components.footer(request),
    )


@rt("/recent")
def get(request):
    "Display the most recently modified reference items."
    auth.allow_anyone(request)

    refs = get_refs()
    items = sorted(list(refs), key=lambda i: i.modified, reverse=True)
    items = items[: constants.MAX_RECENT]

    rows = [
        Tr(
            Td(
                Img(
                    src="/clipboard.svg",
                    title="Copy refid to clipboard",
                    style="cursor: pointer;",
                    cls="white to_clipboard",
                    data_clipboard_action="copy",
                    data_clipboard_text=f"[@{ref['name']}]",
                ),
                components.blank(0.1),
                A(
                    Strong(ref["name"], style=f"color: {constants.REFS_COLOR};"),
                    href=f"/refs/{ref}",
                ),
                components.blank(0.4),
                utils.full_title(ref),
            ),
            Td(ref.modified),
        )
        for ref in items
    ]

    title = Tx("Recently modified")
    return (
        Title(title),
        components.header(request, title, book=refs),
        Main(
            P(Table(Tbody(*rows))),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/bibtex")
def get(request):
    "Add reference(s) from BibTex data."
    title = f'{Tx("Add reference(s)")}: BibTex'
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("BibTex data")),
                    Textarea(name="data", rows=16, autofocus=True),
                ),
                components.save_button("Add reference(s)"),
                action="/refs/bibtex",
                method="post",
            ),
            components.cancel_button(f"/refs"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/bibtex")
def post(request, data: str):
    "Actually add reference(s) using BibTex data."
    result = []
    for entry in bibtexparser.loads(data).entries:
        authors = entry.get("author", "")
        authors = cleanup_latex(authors).replace(" and ", "\n")
        editors = entry.get("editor", "")
        editors = cleanup_latex(editors).replace(" and ", "\n")
        form = {
            "authors": authors + editors,
            "year": entry["year"],
            "type": entry.get("ENTRYTYPE") or constants.ARTICLE,
        }
        for key, value in entry.items():
            if key in ("author", "ID", "ENTRYTYPE"):
                continue
            form[key] = cleanup_latex(value).strip()
        # Do some post-processing.
        # Change month into date; sometimes has day number.
        month = form.pop("month", "")
        parts = month.split("~")
        if len(parts) == 2 and parts[1]:
            month = constants.MONTHS[parts[1].strip().lower()]
            day = int("".join([c for c in parts[0] if c in string.digits]))
            form["date"] = f'{entry["year"]}-{month:02d}-{day:02d}'
        elif len(parts) == 1 and parts[0]:
            month = constants.MONTHS[parts[0].strip().lower()]
            form["date"] = f'{entry["year"]}-{month:02d}-00'
        # Change page numbers double dash to single dash.
        form["pages"] = form.get("pages", "").replace("--", "-")
        # Put abstract into notes.
        abstract = form.pop("abstract", None)
        if abstract:
            form["notes"] = "**Abstract**\n\n" + abstract
        try:
            reference = get_ref_from_form(form)
        except Error:
            pass
        else:
            result.append(reference)

    # Reread the cache.
    refs = get_refs(reread=True)

    title = Tx("Added reference(s)")
    return (
        Title(title),
        components.header(request, title, book=refs),
        Main(
            Ul(*[Li(A(r["name"], href=f'/refs/{r["id"]}')) for r in result]),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/add/{type:str}")
def get(request, type: str):
    "Add reference from scratch."
    title = f'{Tx("Add reference")}: {Tx(type)}'
    return (
        Title(title),
        components.header(request, title, book=get_refs()),
        Main(
            Form(
                *get_ref_fields(type=type),
                components.save_button("Add reference"),
                action=f"/refs/add",
                method="post",
            ),
            components.cancel_button("/refs"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/add")
def post(request, form: dict):
    "Actually add reference from scratch."
    ref = get_ref_from_form(form)
    get_refs(reread=True)

    return components.redirect(f"/refs/{ref['id']}")


@rt("/delete/{ref:Ref}")
def get(request, ref: Text):
    "Confirm delete of the text or section; section must be empty."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)

    if ref.content:
        segments = [P(Strong(Tx("Note: all contents will be lost!")))]
    else:
        segments = []

    title = f"{Tx('Delete')} '{ref['name']}'?"
    return (
        Title(title),
        components.header(request, title, book=get_refs(), status=ref.status),
        Main(
            H3(Tx("Delete"), "?"),
            *segments,
            Form(
                components.save_button("Confirm"),
                action=f"/refs/delete/{ref['id']}",
                method="post",
            ),
            components.cancel_button(f"/refs/{ref['id']}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/delete/{ref:Ref}")
def post(request, ref: Text):
    "Actually delete the reference."
    auth.authorize(request, *auth.ref_edit_rules, ref=ref)
    ref.delete(force=True)
    return components.redirect("/refs")


@rt("/search")
def post(request, form: dict):
    "Actually search the references for a given term."
    auth.allow_anyone(request)

    refs = get_refs()
    term = form.get("term")
    if term:
        # Ignore case only when term is in all lower-case.
        ignorecase = term == term.lower()
        items = [
            Li(A(i.fulltitle, href=f"/refs/{i.path}"))
            for i in sorted(
                refs.search(utils.wildcard_to_regexp(term), ignorecase=ignorecase),
                key=lambda i: i.ordinal,
            )
        ]
        if items:
            result = P(Ul(*items))
        else:
            result = P(f'{Tx("No result")}.')
    else:
        result = P()

    title = f"{Tx('Search in')} {Tx('references')}"
    return (
        Title(title),
        components.header(request, title, book=refs),
        Main(
            components.search_form(f"/refs/search", term=term),
            result,
            cls="container",
        ),
    )


@rt("/all.tgz")
def get(request):
    "Download a gzipped tar file of the references."
    auth.allow_anyone(request)

    filename = f"writethatbook_refs_{utils.timestr(safe=True)}.tgz"

    return Response(
        content=get_refs().get_tgz_content(),
        media_type=constants.GZIP_MIMETYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@rt("/upload")
def get(request):
    """Upload a gzipped tar file of references;
    replace any reference with the same name.
    """
    refs = get_refs()
    auth.authorize(request, *auth.refs_edit_rules, refs=refs)

    title = Tx("Upload reference(s)")
    return (
        Title(title),
        components.header(request, title, book=refs),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("Reference(s) TGZ file"), components.required()),
                    Input(type="file", name="tgzfile", required=True),
                ),
                components.save_button("Upload"),
                action="/refs/upload",
                method="post",
            ),
            components.cancel_button("/refs"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/upload")
async def post(request, tgzfile: UploadFile):
    "Actually add or replace references by contents of the uploaded file."
    auth.authorize(request, *auth.refs_edit_rules, book=get_refs())

    content = await tgzfile.read()
    if not content:
        raise Error("empty TGZ file")
    books.unpack_tgz_content(get_refs().abspath, content)
    get_refs(reread=True)

    return components.redirect("/refs")


def get_ref_fields(ref=None, type=None):
    "Return list of input fields for adding or editing a reference."
    if type is None:
        return Fieldset(
            Legend(Tx("Type")),
            Select(
                *[
                    Option(Tx(t.capitalize()), value=t)
                    for t in constants.REFERENCE_TYPES
                ],
                name="type",
            ),
        )

    else:
        result = [Input(type="hidden", name="type", value=type)]
    if ref is None:
        ref = {}
        autofocus = True
    else:
        autofocus = False
    result.append(
        Fieldset(
            Legend(Tx("Authors"), components.required()),
            Textarea(
                "\n".join(ref.get("authors") or []),
                name="authors",
                required=True,
                autofocus=autofocus,
            ),
        )
    )
    result.append(
        Fieldset(
            Legend(Tx("Title"), components.required()),
            Input(name="title", value=ref.get("title") or "", required=True),
        )
    )
    if type == constants.BOOK:
        result.append(
            Fieldset(
                Legend(Tx("Subtitle")),
                Input(name="subtitle", value=ref.get("subtitle") or ""),
            )
        )
    # The year cannot be edited once the reference has been created.
    if ref:
        result.append(Input(type="hidden", name="year", value=ref["year"]))
    else:
        result.append(
            Fieldset(
                Legend(Tx("Year"), components.required()),
                Input(name="year", value=ref.get("year") or "", required=True),
            )
        )
    # Both a book and an article may have been reprinted.
    if type in (constants.BOOK, constants.ARTICLE):
        result.append(
            Fieldset(
                Legend(Tx("Edition published")),
                Input(
                    name="edition_published", value=ref.get("edition_published") or ""
                ),
            )
        )
    result.append(
        Fieldset(Legend(Tx("Date")), Input(name="date", value=ref.get("date") or ""))
    )
    if type == constants.ARTICLE:
        result.append(
            Fieldset(
                Legend(Tx("Journal") + " / " + Tx("Part of") + " " + Tx("reference")),
                Input(name="journal", value=ref.get("journal") or ""),
            )
        )
        result.append(
            Fieldset(
                Legend(Tx("Volume")),
                Input(name="volume", value=ref.get("volume") or ""),
            )
        )
        result.append(
            Fieldset(
                Legend(Tx("Number")),
                Input(name="number", value=ref.get("number") or ""),
            )
        )
        result.append(
            Fieldset(
                Legend(Tx("Pages")), Input(name="pages", value=ref.get("pages") or "")
            )
        )
        result.append(
            Fieldset(
                Legend(Tx("ISSN")), Input(name="issn", value=ref.get("issn") or "")
            )
        )
        result.append(
            Fieldset(
                Legend(Tx("PubMed")), Input(name="pmid", value=ref.get("pmid") or "")
            )
        )
    if type == constants.BOOK:
        result.append(
            Fieldset(
                Legend(Tx("ISBN")), Input(name="isbn", value=ref.get("isbn") or "")
            )
        )
    if type in (constants.BOOK, constants.ARTICLE):
        result.append(
            Fieldset(Legend(Tx("DOI")), Input(name="doi", value=ref.get("doi") or ""))
        )
    result.append(
        Fieldset(Legend(Tx("URL")), Input(name="url", value=ref.get("url") or ""))
    )
    result.append(
        Fieldset(
            Legend(Tx("Publisher")),
            Input(name="publisher", value=ref.get("publisher") or ""),
        )
    )
    result.append(
        Fieldset(
            Legend(Tx("Language")),
            Input(name="language", value=ref.get("language") or ""),
        )
    )
    result.append(
        Fieldset(
            Legend(Tx("Keywords")),
            Input(name="keywords", value="; ".join(ref.get("keywords") or [])),
        )
    )
    if ref:
        content = ref.content or ""
        autofocus = True
    else:
        content = ""
        autofocus = False
    result.append(
        Fieldset(
            Legend(Tx("Notes")),
            Textarea(content, name="notes", rows=16, autofocus=autofocus),
        )
    )
    return result


def get_ref_from_form(form, ref=None):
    "Set the values of the reference from the form."
    if ref is None:
        type = form.get("type", "").strip()
        if type not in constants.REFS_TYPES:
            raise Error(f"invalid reference type '{type}'")
    authors = [s.strip() for s in form.get("authors", "").split("\n") if s.strip()]
    if not authors:
        raise Error("no author(s) provided")
    title = cleanup_whitespaces(form.get("title", ""))
    if not title:
        raise Error("no title provided")
    year = form.get("year", "").strip()
    if not year:
        raise Error("no year provided")

    if ref is None:
        author = authors[0].split(",")[0].strip()
        for char in [""] + list(string.ascii_lowercase):
            name = f"{author} {year}{char}"
            refid = utils.nameify(name)
            if get_refs().get(refid) is None:
                break
        else:
            raise Error(f"could not form unique id for {name} {year}")
        try:
            ref = get_refs().create_text(name)
        except ValueError as message:
            raise Error(message)
        ref.set("type", type)
        ref.set("id", refid)
        ref.set("name", name)

    # Don't bother selecting keys to add according to type...
    ref.set("authors", authors)
    ref.set("title", title)
    ref.set("year", year)
    ref.set("subtitle", cleanup_whitespaces(form.get("subtitle", "")))
    ref.set("edition_published", form.get("edition_published", "").strip())
    ref.set("date", form.get("date", "").strip())
    ref.set("journal", cleanup_whitespaces(form.get("journal", "")))
    ref.set("volume", form.get("volume", "").strip())
    ref.set("number", form.get("number", "").strip())
    ref.set("pages", form.get("pages", "").strip())
    ref.set("language", form.get("language", "").strip())
    ref.set("publisher", form.get("publisher", "").strip())
    ref.set(
        "keywords",
        [s.strip() for s in form.get("keywords", "").split(";") if s.strip()],
    ),
    ref.set("issn", form.get("issn", "").strip())
    ref.set("isbn", form.get("isbn", "").strip())
    ref.set("pmid", form.get("pmid", "").strip())
    ref.set("doi", form.get("doi", "").strip())
    ref.set("url", form.get("url", "").strip())
    ref.write(content=form.get("notes", "").strip())
    return ref


def cleanup_latex(value):
    "Convert LaTeX characters to UTF-8, remove newlines and normalize blanks."
    return latex_utf8.from_latex_to_utf8(" ".join(value.split()))


def cleanup_whitespaces(value):
    "Replace all whitespaces with blanks."
    return " ".join([s for s in value.split()])
