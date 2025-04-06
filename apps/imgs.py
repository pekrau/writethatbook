"Images list, view, and edit pages."

import base64
import json
import os.path

import babel.numbers
from fasthtml.common import *
import vl_convert

import auth
import books
from books import get_imgs, Text
import components
import constants
import markdown
import minixml
import utils
from utils import Tx


class ImgConvertor(Convertor):
    regex = "[a-z0-9-]+"

    def convert(self, value: str) -> Text:
        return get_imgs()[value]

    def to_string(self, value: Text) -> str:
        return value["id"]


register_url_convertor("Img", ImgConvertor())


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Table of images."
    auth.allow_anyone(request)

    imgs = get_imgs()
    items = [i for i in imgs if auth.authorized(request, *auth.img_view, img=i)]
    rows = []
    for img in items:
        rows.append(
            Tr(
                Td(A(img["title"], href=f"/imgs/view/{img['id']}")),
                Td(get_img_clipboard(img, img["id"])),
                Td(constants.IMAGE_MAP[img["content_type"]]),
                Td(Tx(img.status), title=Tx("Status")),
                Td(utils.str_datetime_display(img.modified), title=Tx("Modified")),
            )
        )

    table = Table(
        Thead(
            Tr(
                Th(Tx("Image"), scope="col", colspan="2"),
                Th(Tx("Type"), scope="col"),
                Th(Tx("Status"), scope="col"),
                Th(Tx("Modified"), scope="col"),
            )
        ),
        Tbody(*rows),
    )

    tools = []
    if auth.authorized(request, *auth.img_add):
        tools.append((Tx("Add image"), f"/imgs/add"))

    title = f"{len(items)} {Tx('items')}"
    return (
        Title(title),
        Script(src="/clipboard.min.js"),
        Script("new ClipboardJS('.to_clipboard');"),
        components.header(request, title, book=imgs, tools=tools),
        Main(table, cls="container"),
        components.footer(request),
    )


@rt("/view/{img:Img}")
def get(request, img: Text):
    "View an image and its information."
    auth.authorize(request, *auth.img_view, img=img)

    tools = []
    if auth.authorized(request, *auth.img_edit, img=img):
        tools.extend(
            [
                ("Edit", f"/imgs/edit/{img['id']}"),
                ("Delete", f"/imgs/delete/{img['id']}"),
            ]
        )
    if auth.authorized(request, *auth.img_add):
        tools.append((Tx("Add image"), f"/imgs/add"))

    # SVG image.
    if img["content_type"] == constants.SVG_CONTENT_TYPE:
        image = NotStr(img["data"])

    # JSON: Vega-Lite specification image.
    elif img["content_type"] == constants.JSON_CONTENT_TYPE:
        image = NotStr(vl_convert.vegalite_to_svg(json.loads(img["data"])))

    # PNG or JPEG formats.
    else:
        url = f'data:{img["content_type"]};base64, {img["data"]}'
        image = Img(src=url, title=img["title"])

    if img.content:
        item = Article(image, Footer(NotStr(markdown.to_html(img.content))))
    else:
        item = Article(image)

    pdf_info = [
        P(Tx("Scale factor"), ": ", utils.numerical(img["pdf"]["scale_factor"]))
    ]
    if img["content_type"] in (constants.SVG_CONTENT_TYPE, constants.JSON_CONTENT_TYPE):
        pdf_info.append(
            P(
                Tx("Rendering"),
                ": ",
                img["pdf"]["reportlab_graphics"]
                and "ReportLab graphics"
                or "PNG vl_convert",
            )
        )
        pdf_info.append(
            P(
                f'{Tx("PNG factor")}: {utils.numerical(img["pdf"].get("png_rendering_factor"))}'
            )
        )
    docx_info = [
        P(Tx("Scale factor"), ": ", utils.numerical(img["docx"]["scale_factor"]))
    ]

    if img["content_type"] in (constants.SVG_CONTENT_TYPE, constants.JSON_CONTENT_TYPE):
        docx_info.append(
            P(
                f'{Tx("PNG factor")}: {utils.numerical(img["docx"].get("png_rendering_factor"))}'
            )
        )

    title = img["title"]
    return (
        Title(title),
        Script(src="/clipboard.min.js"),
        Script("new ClipboardJS('.to_clipboard');"),
        components.header(request, title, book=get_imgs(), item=img, tools=tools),
        Main(
            item,
            Div(
                P(get_img_clipboard(img, img["id"])),
                P(Tx("Type"), ": ", constants.IMAGE_MAP[img["content_type"]]),
                cls="grid",
            ),
            Div(
                Article(Header("PDF"), *pdf_info),
                Article(Header("DOCX"), *docx_info),
                cls="grid",
            ),
            cls="container",
        ),
        components.footer(request, img),
    )


@rt("/add")
def get(request):
    "Display forms page for adding an image."
    auth.authorize(request, *auth.img_add)

    title = Tx("Add image")
    return (
        Title(title),
        components.header(request, title, book=get_imgs()),
        Main(
            Form(
                Fieldset(
                    Label(Tx("Title")),
                    Input(name="title", autofocus=True),
                ),
                Fieldset(
                    Label(Tx("Image file"), components.required()),
                    Input(type="file", name="image_file", multiple=False),
                ),
                Fieldset(
                    Label(Tx("Caption")),
                    Textarea(name="caption"),
                ),
                components.save_button("Add image"),
                action=f"/imgs/add",
                method="post",
            ),
            components.cancel_button("/imgs"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/add")
async def post(session, request, form: dict):
    "Actually add an image."
    auth.authorize(request, *auth.img_add)

    imgs = get_imgs()

    image_file = form["image_file"]
    if image_file.size == 0:
        add_toast(session, "No image file given.", "error")
        return components.redirect("/imgs/add")
    title = form.get("title")
    caption = form.get("caption")
    filename = os.path.splitext(image_file.filename)[0]
    imgid = utils.nameify(filename)
    try:
        img = imgs.create_text(imgid)
    except ValueError as message:
        raise Error(message)
    img["id"] = imgid
    img.title = title or imgid
    img["content_type"] = image_file.content_type
    image_content = await image_file.read()
    img["pdf"] = dict(scale_factor=constants.PDF_DEFAULT_IMAGE_SCALE_FACTOR)
    img["docx"] = dict(scale_factor=constants.DOCX_DEFAULT_IMAGE_SCALE_FACTOR)

    # SVG image.
    if image_file.content_type == constants.SVG_CONTENT_TYPE:
        try:
            root = parse_check_svg(image_content.decode("utf-8"))
        except ValueError as error:
            add_toast(session, str(error), "error")
            return components.redirect("/imgs/add")
        root.repr_indent = None
        root.xml_decl = False
        img["data"] = repr(root)
        img["base64"] = False
        img["pdf"]["reportlab_graphics"] = True
        img["pdf"]["png_rendering_factor"] = constants.PDF_DEFAULT_PNG_RENDERING_FACTOR
        img["docx"][
            "png_rendering_factor"
        ] = constants.DOCX_DEFAULT_PNG_RENDERING_FACTOR
        # Set caption from SVG description, if not set.
        if not caption:
            desc = list(root.walk(lambda e: e.tag == "desc" and e.depth == 1))
            if desc:
                caption = desc[0].text

    # Vega-Lite specification.
    elif image_file.content_type == constants.JSON_CONTENT_TYPE:
        try:
            spec = parse_check_vegalite(image_content)
        except ValueError as error:
            add_toast(session, str(error), "error")
            return components.redirect("/imgs/add")
        img["data"] = json.dumps(spec, ensure_ascii=False)
        img["base64"] = False
        img["pdf"]["reportlab_graphics"] = True
        img["pdf"]["png_rendering_factor"] = constants.DOCX_DEFAULT_PNG_RENDERING_FACTOR
        img["docx"][
            "png_rendering_factor"
        ] = constants.DOCX_DEFAULT_PNG_RENDERING_FACTOR
        # Set caption from Vega-Lite description, if not set.
        if not caption:
            caption = spec.get("description")

    # PNG and JPEG formats.
    elif image_file.content_type in (
        constants.PNG_CONTENT_TYPE,
        constants.JPEG_CONTENT_TYPE,
    ):
        img["data"] = base64.standard_b64encode(image_content).decode("utf-8")
        img["base64"] = True
    else:
        return Error(f"invalid image file content type '{image_file.content_type}'")

    # Caption may have been set from image contents.
    img.write(content=caption)

    return components.redirect(f"/imgs/view/{img['id']}")


@rt("/edit/{img:Img}")
def get(request, img: Text):
    "Edit the image."
    auth.authorize(request, *auth.img_edit, img=img)

    # SVG image.
    if img["content_type"] == constants.SVG_CONTENT_TYPE:
        root = minixml.parse_content(img["data"])
        root.xml_decl = False
        edit_fieldset = Fieldset(
            Label("SVG"),
            Textarea(repr(root), name="image_text", rows=16),
        )

    # Vega-Lite specification.
    elif img["content_type"] == constants.JSON_CONTENT_TYPE:
        spec = json.loads(img["data"])
        edit_fieldset = Fieldset(
            Label("Vega-Lite"),
            Textarea(
                json.dumps(spec, indent=2, ensure_ascii=False),
                name="image_text",
                rows=16,
            ),
        )

    # Un-editable image content such as PNG and JPEG images.
    else:
        edit_fieldset = (
            Fieldset(
                Label(Tx("Image file")),
                Input(type="file", name="image_file", multiple=False),
            ),
        )

    fieldsets = [
        Fieldset(
            Label(Tx("Title")),
            Input(name="title", value=img.title, autofocus=True),
        ),
        edit_fieldset,
        Fieldset(
            Label(Tx("Caption")),
            Textarea(img.content or "", name="caption"),
        ),
        Fieldset(
            Label(Tx("Status")),
            components.get_status_field(img),
        ),
    ]

    pdf_scale_factor = [
        Label(Tx("Scale factor")),
        Input(
            type="number",
            name="pdf_scale_factor",
            min=0.1,
            max=2.0,
            step=0.1,
            value=img["pdf"]["scale_factor"],
        ),
    ]

    docx_scale_factor = [
        Label(Tx("Scale factor")),
        Input(
            type="number",
            name="docx_scale_factor",
            min=0.1,
            max=2.0,
            step=0.1,
            value=img["docx"]["scale_factor"],
        ),
    ]

    # SVG image and Vega-Lite specification.
    if img["content_type"] in (constants.SVG_CONTENT_TYPE, constants.JSON_CONTENT_TYPE):
        pdf_fieldset = Fieldset(
            Legend(
                Tx("Rendering"),
                Label(
                    Input(
                        type="radio",
                        name="pdf_reportlab_graphics",
                        checked=img["pdf"]["reportlab_graphics"],
                        value="true",
                    ),
                    "ReportLab graphics",
                ),
                Label(
                    Input(
                        type="radio",
                        name="pdf_reportlab_graphics",
                        checked=not img["pdf"]["reportlab_graphics"],
                        value="false",
                    ),
                    "PNG vl_convert",
                ),
            ),
            Label(Tx("PNG factor")),
            Input(
                type="number",
                name="pdf_png_rendering_factor",
                min=1,
                max=8,
                step=1,
                value=img["pdf"].get(
                    "png_rendering_factor", constants.PDF_DEFAULT_PNG_RENDERING_FACTOR
                ),
            ),
            *pdf_scale_factor,
        )
        docx_fieldset = Fieldset(
            Label(Tx("PNG factor")),
            Input(
                type="number",
                name="docx_png_rendering_factor",
                min=1,
                max=8,
                step=1,
                value=img["docx"].get(
                    "png_rendering_factor", constants.DOCX_DEFAULT_PNG_RENDERING_FACTOR
                ),
            ),
            *docx_scale_factor,
        )

    # PNG and JPEG images.
    else:
        pdf_fieldset = Fieldset(*pdf_scale_factor)
        docx_fieldset = Fieldset(*docx_scale_factor)

    title = Tx("Edit image")
    return (
        Title(title),
        components.header(request, title, book=get_imgs(), item=img),
        Main(
            Form(
                *fieldsets,
                Div(
                    Article(Header("PDF"), pdf_fieldset),
                    Article(Header("DOCX"), docx_fieldset),
                    cls="grid",
                ),
                components.save_button("Save"),
                action=f"/imgs/edit/{img['id']}",
                method="post",
            ),
            components.cancel_button(f"/imgs/view/{img['id']}"),
            cls="container",
        ),
        components.footer(request, item=img),
    )


@rt("/edit/{img:Img}")
async def post(session, request, img: Text, form: dict):
    "Actually edit the image."
    auth.authorize(request, *auth.img_edit, img=img)

    image_text = form.get("image_text")
    image_file = form.get("image_file")
    title = form.get("title")
    caption = form.get("caption")
    status = form.get("status")

    if img["content_type"] == constants.SVG_CONTENT_TYPE:
        if image_text:
            try:
                root = parse_check_svg(image_text)
            except ValueError as error:
                add_toast(session, str(error), "error")
                return components.redirect(f"/imgs/edit/{img['id']}")
            root.repr_indent = None
            root.xml_decl = False
            img["data"] = repr(root)
            # Set caption from SVG description, if not set.
            if not caption:
                desc = list(root.walk(lambda e: e.tag == "desc" and e.depth == 1))
                if desc:
                    caption = desc[0].text

    elif img["content_type"] == constants.JSON_CONTENT_TYPE:
        if image_text:
            try:
                spec = parse_check_vegalite(image_text)
            except ValueError as error:
                add_toast(session, str(error), "error")
                return components.redirect(f"/imgs/edit/{img['id']}")
            img["data"] = json.dumps(spec, ensure_ascii=False)
            # Set caption from Vega-Lite description, if not set.
            if not caption:
                caption = spec.get("description")

    # PNG and JPEG formats.
    elif img["content_type"] in (
        constants.PNG_CONTENT_TYPE,
        constants.JPEG_CONTENT_TYPE,
    ):
        if image_file and image_file.size != 0:
            if image_file.content_type not in (
                constants.PNG_CONTENT_TYPE,
                constants.JPEG_CONTENT_TYPE,
            ):
                add_toast(session, "File must be PNG or JPEG.", "error")
                return components.redirect(f"/imgs/edit/{img['id']}")
            # Allow changing between PNG and JPEG formats.
            image_content = await image_file.read()
            img["content_type"] = image_file.content_type
            img["data"] = base64.standard_b64encode(image_content).decode("utf-8")
            img["base64"] = True

    else:
        return Error(f"invalid image file content type '{image_file.content_type}'")

    img["pdf"]["scale_factor"] = float(form["pdf_scale_factor"])
    try:
        img["pdf"]["reportlab_graphics"] = (
            form["pdf_reportlab_graphics"].lower() == "true"
        )
    except KeyError:
        pass
    try:
        img["pdf"]["png_rendering_factor"] = int(form["pdf_png_rendering_factor"])
    except KeyError:
        pass

    img["docx"]["scale_factor"] = float(form["docx_scale_factor"])
    try:
        img["docx"]["png_rendering_factor"] = int(form["docx_png_rendering_factor"])
    except KeyError:
        pass

    img.title = title or img["id"]
    if status:
        img.status = status
    # Caption may have been set from image contents.
    img.write(content=caption)

    return components.redirect(f"/imgs/view/{img['id']}")


@rt("/delete/{img:Img}")
def get(request, img: Text):
    "Confirm delete of the image text item."
    auth.authorize(request, *auth.img_edit, img=img)

    title = f"{Tx('Delete')} '{img['title']}'?"
    return (
        Title(title),
        components.header(request, title, book=get_imgs(), item=img),
        Main(
            H3(Tx("Delete"), "?"),
            P(Strong(Tx("Note: all contents will be lost!"))),
            Form(
                components.save_button("Confirm"),
                action=f"/imgs/delete/{img['id']}",
                method="post",
            ),
            components.cancel_button(f"/imgs/view/{img['id']}"),
            cls="container",
        ),
        components.footer(request),
    )


@rt("/delete/{img:Img}")
def post(request, img: Text):
    "Actually delete the image text item."
    auth.authorize(request, *auth.img_edit, img=img)
    img.delete(force=True)
    return components.redirect("/imgs")


def parse_check_svg(content):
    """Check that SVG contains 'svg' root and 'width' and 'height' attributes.
    Raise ValueError if any problem.
    Adds SVG xmlns if not present.
    Returns the minixml root element.
    """
    root = minixml.parse_content(content)
    if root.tag != "svg":
        raise ValueError("XML root element must be 'svg'.")
    for key in ["width", "height"]:
        if key not in root:
            raise ValueError(f"XML 'svg' element must contain attribute '{key}'.")
        try:
            value = float(root[key])
            if value <= 0:
                raise ValueError
        except ValueError:
            raise ValueError(f"XML 'svg' attribute '{key}' must be positive number.")
    # Root 'svg' element must contain xmlns; add if missing.
    if "xmlns" not in root:
        root["xmlns"] = constants.SVG_XMLNS
    return root


def parse_check_vegalite(content):
    """Check that content is valid JSON and can be handled by vl_convert.
    Raise ValueError if any problem.
    Returns the JSON specification.
    """
    try:
        spec = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(str(error))
    vl_convert.vegalite_to_svg(spec)
    return spec


def get_img_clipboard(img, text):
    return Span(
        Img(
            src="/clipboard.svg",
            cls="white",
        ),
        " ",
        text,
        style="cursor: pointer;",
        title=Tx("Copy image to clipboard"),
        cls="to_clipboard",
        data_clipboard_action="copy",
        data_clipboard_text=f"![{img.content}]({img['id']})",
    )
