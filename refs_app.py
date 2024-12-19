"References list, view and edit."

from icecream import ic

import string

import bibtexparser
from fasthtml.common import *

import auth
from books import Text, get_refs, get_books
import components
import constants
import utils
from utils import Tx


class RefConvertor(Convertor):
    regex = "[a-z-]+-[0-9]+[a-z]*"

    def convert(self, value: str) -> Text:
        return get_refs()[value]

    def to_string(self, value: Text) -> str:
        return value["id"]


register_url_convertor("Ref", RefConvertor())


app, rt = utils.get_fast_app()


@rt("/")
def get(request):
    "List of references."
    auth.allow_anyone(request)

    refs = get_refs()
    refs.write()  # Updates the 'index.md' file, if necessary.
    items = []
    for ref in refs.items:
        parts = [
            Img(
                src="/clipboard.svg",
                title="Copy refid to clipboard",
                style="cursor: pointer;",
                cls="to_clipboard",
                data_clipboard_text=f"[@{ref['name']}]",
            ),
            components.blank(0.2),
            A(
                Strong(ref["name"], style=f"color: {constants.REFS_COLOR};"),
                href=f'/refs/{ref}',
            ),
            components.blank(0.4),
        ]
        if ref.get("authors"):
            authors = [utils.short_name(a) for a in ref["authors"]]
            if len(authors) > constants.MAX_DISPLAY_AUTHORS:
                authors = authors[: constants.MAX_DISPLAY_AUTHORS] + ["..."]
            parts.append(", ".join(authors))
        parts.append(Br())
        parts.append(utils.full_title(ref))

        links = []
        if ref["type"] == constants.ARTICLE:
            parts.append(Br())
            if ref.get("journal"):
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
            parts.append(Br())
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
            parts.append(Br())
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
        for book in get_books(request):
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

    pages = [("Keywords", "/refs/keywords")]
    actions = [
        (f'{Tx("Add reference")}: {Tx(type)}', f"/refs/add/{type}")
        for type in constants.REFS_TYPES
    ]
    actions.append([f'{Tx("Add reference(s)")}: BibTex', "/refs/bibtex"])
    # menu.append(A(Tx("Recently modified"), href="/recent/refses"))
    # menu.append(
    #     A(
    #         f'{Tx("Download")} {Tx("references")} {Tx("TGZ file")}',
    #         href="/tgz/references",
    #     )
    # )
    # menu.append(
    #     A(
    #         f'{Tx("Upload")} {Tx("references")} {Tx("TGZ file")}',
    #         href="/references/upload",
    #     )
    # )
    # menu.append(A(Tx("State (JSON)"), href="/state/references"))
    # if "WRITETHATBOOK_UPDATE_SITE" in os.environ:
    #     menu.append(A(Tx("Differences"), href="/differences/references"))

    title = f'{Tx("References")} ({len(refs.items)})'
    return (
        Title(title),
        components.header(request, title, actions=actions, pages=pages),
        Main(components.search_form(f"/search/references"), *items, cls="container"),
    )


@rt("/{ref:Ref}")
def get(request, ref: Text):
    "Display a reference."
    auth.allow_anyone(request)

    rows = [
        Tr(
            Td(Tx("Reference")),
            Td(
                f"{ref['name']}",
                components.blank(0.2),
                Img(
                    src="/clipboard.svg",
                    title=Tx("Reference to clipboard"),
                    style="cursor: pointer;",
                    cls="to_clipboard",
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
        "journal",
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
    for book in get_books(request):
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
    rows.append(Tr(Td(Tx("Referenced by"), valign="top"), Td(*xrefs)))

    actions = [
        # A(
        #     Tx("Clipboard"),
        #     href="#",
        #     cls="to_clipboard",
        #     data_clipboard_text=f'[@{ref["name"]}]',
        # ),
        ("Edit", f"/refs/edit/{ref['id']}"),
        # A(Tx("Append"), href=f"/append/references/{refid}"),
        # A(Tx("Delete"), href=f"/delete/references/{refid}"),  # Yes, plural.
    ]

    title = f"{ref['name']} ({Tx(ref['type'])})"
    edit_buttons = Div(
        Div(A(Tx("Edit"), role="button", href=f"/refs/edit/{ref['id']}")),
        Div(A(Tx("Append"), role="button", href=f"/refs/append/{ref['id']}")),
        cls="grid",
    )
    return (
        Title(title),
        Script(src="/clipboard.min.js"),
        Script("new ClipboardJS('.to_clipboard');"),
        components.header(request, title, book=get_refs(), status=ref.status, actions=actions),
        Main(
            Table(*rows),
            edit_buttons,
            Div(NotStr(ref.html), style="margin-top: 1em;"),
            edit_buttons,
            cls="container",
        ),
        components.footer(ref),
    )


@rt("/edit/{ref:Ref}")
def get(request, ref: Text):
    "Edit a reference."
    title = f"{Tx('Edit')} '{ref['name']}' ({Tx(ref['type'])})"
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                *get_ref_fields(ref=ref, type=ref["type"]),
                components.get_status_field(ref),
                Button(Tx("Save")),
                action=f"/refs/edit/{ref['id']}",
                method="post",
            ),
            components.cancel_button(f"/refs/{ref['id']}"),
            cls="container",
        ),
    )


@rt("/edit/{ref:Ref}")
def post(request, ref: Text, form: dict):
    "Actually edit the reference."
    try:
        ref.status = form.pop("status")
    except KeyError:
        pass
    get_ref_from_form(form, ref=ref)
    get_refs(reread=True)

    return utils.redirect(f"/refs/{ref['id']}")


@rt("/keywords")
def get(request):
    "List the keyword terms of the references."
    auth.allow_anyone(request)

    refs = get_refs()
    items = []
    for key, texts in sorted(refs.indexed.items(), key=lambda tu: tu[0].lower()):
        refs = []
        for text in sorted(texts, key=lambda t: t.ordinal):
            refs.append(
                Li(
                    A(
                        f'{text["name"]}: {text.fulltitle}',
                        cls="secondary",
                        href=f"/refs/{text.path}",
                    )
                )
            )
        items.append(Li(key, Small(Ul(*refs))))

    title = f'{Tx("Keywords")}, {Tx("references")}'
    return (
        Title(title),
        components.header(request, title),
        Main(Ul(*items), cls="container"),
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
                    Textarea(name="data", rows="20", autofocus=True),
                ),
                Button("Add reference(s)"),
                action="/refs/bibtex",
                method="post",
            ),
            components.cancel_button(f"/refs"),
            cls="container",
        ),
    )


@rt("/bibtex")
def post(request, data: str):
    "Actually add reference(s) using BibTex data."
    result = []
    for entry in bibtexparser.loads(data).entries:
        form = {
            "authors": utils.cleanup_latex(entry["author"]).replace(" and ", "\n"),
            "year": entry["year"],
            "type": entry.get("ENTRYTYPE") or constants.ARTICLE,
        }
        for key, value in entry.items():
            if key in ("author", "ID", "ENTRYTYPE"):
                continue
            form[key] = utils.cleanup_latex(value).strip()
        # Do some post-processing.
        # Change month into date; sometimes has day number.
        month = form.pop("month", "")
        parts = month.split("~")
        if len(parts) == 2:
            month = constants.MONTHS[parts[1].strip().lower()]
            day = int("".join([c for c in parts[0] if c in string.digits]))
            form["date"] = f'{entry["year"]}-{month:02d}-{day:02d}'
        elif len(parts) == 1:
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
    )


@rt("/add/{type:str}")
def get(request, type: str):
    "Add reference from scratch."
    title = f'{Tx("Add reference")}: {Tx(type)}'
    return (
        Title(title),
        components.header(request, title),
        Main(
            Form(
                *get_ref_fields(type=type),
                Button(Tx("Add reference")),
                action=f"/refs/add",
                method="post",
            ),
            components.cancel_button("/refs"),
            cls="container",
        ),
    )


@rt("/add")
def post(request, form: dict):
    "Actually add reference from scratch."
    ref = get_ref_from_form(form)
    get_refs(reread=True)

    return utils.redirect(f"/refs/{ref['id']}")


def get_ref_fields(ref=None, type=None):
    """Return list of input fields for adding or editing a reference.
    """
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
                Legend(Tx("Journal")),
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
            Textarea(content, name="notes", rows=10, autofocus=autofocus),
        )
    )
    return result


def get_ref_from_form(form, ref=None):
    "Set the values of the reference from a form."
    if ref is None:
        type = form.get("type", "").strip()
        if type not in constants.REFS_TYPES:
            raise Error(f"invalid reference type '{type}'")
    authors = [s.strip() for s in form.get("authors", "").split("\n") if s.strip()]
    if not authors:
        raise Error("no author(s) provided")
    title = utils.cleanup_whitespaces(form.get("title", ""))
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
    ref.set("subtitle", utils.cleanup_whitespaces(form.get("subtitle", "")))
    ref.set("edition_published", form.get("edition_published", "").strip())
    ref.set("date", form.get("date", "").strip())
    ref.set("journal", utils.cleanup_whitespaces(form.get("journal", "")))
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
