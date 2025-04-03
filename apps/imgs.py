"Images list, view, and edit pages."

import base64
import json
import os.path

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
                Td(constants.IMAGE_MAP[img["content_type"]]),
                Td(Tx(img.status), title=Tx("Status")),
                Td(utils.str_datetime_display(img.modified), title=Tx("Modified")),
            )
        )

    table = Table(
        Thead(
            Tr(
                Th(Tx("Image"), scope="col"),
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

    # SVG image.
    if img["content_type"] == constants.SVG_CONTENT_TYPE:
        image = NotStr(img["image"])

    # JSON: Vega-Lite specification image.
    elif img["content_type"] == constants.JSON_CONTENT_TYPE:
        image = NotStr(vl_convert.vegalite_to_svg(json.loads(img["image"])))

    # PNG or JPEG formats.
    else:
        url = f'data:{img["content_type"]};base64, {img["image"]}'
        image = Img(src=url, title=img["title"])

    if img.content:
        item = Article(image, Footer(NotStr(markdown.to_html(img.content))))
    else:
        item = Article(image)

    title = img["title"]
    return (
        Title(title),
        components.header(request, title, book=get_imgs(), item=img, tools=tools),
        Main(
            item,
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
                    Legend(Tx("Title")),
                    Input(name="title", autofocus=True),
                ),
                Fieldset(
                    Legend(Tx("Image file"), components.required()),
                    Input(type="file", name="image_file", multiple=False),
                ),
                Fieldset(
                    Legend(Tx("Caption")),
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
    img.set("id", imgid)
    img.title = title or imgid
    img.set("content_type", image_file.content_type)
    image_content = await image_file.read()

    # SVG image.
    if image_file.content_type == constants.SVG_CONTENT_TYPE:
        try:
            root = parse_check_svg(image_content.decode("utf-8"))
        except ValueError as error:
            add_toast(session, str(error), "error")
            return components.redirect("/imgs/add")
        root.repr_indent = None
        root.xml_decl = False
        img.set("image", repr(root))
        img.set("base64", False)
        # Set caption from SVG description, if not set.
        if not caption:
            desc = list(root.walk(lambda e: e.tag == "desc" and e.depth == 1))
            if desc:
                caption = desc[0].text

    # Vega-Lite specification.
    elif image_file.content_type == constants.JSON_CONTENT_TYPE:
        try:
            spec = parse_check_vegalite(image_content)[1]
        except ValueError as error:
            add_toast(session, str(error), "error")
            return components.redirect("/imgs/add")
        img.set("image", json.dumps(spec))
        img.set("base64", False)
        # Set caption from Vega-Lite description, if not set.
        if not caption:
            caption = spec.get("description")

    # PNG and JPEG formats.
    elif image_file.content_type in (
        constants.PNG_CONTENT_TYPE,
        constants.JPEG_CONTENT_TYPE,
    ):
        img.set("image", base64.standard_b64encode(image_content).decode("utf-8"))
        img.set("base64", True)
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
        root = minixml.parse_content(img["image"])
        root.xml_decl = False
        fieldset = Fieldset(
            Legend("SVG"),
            Textarea(repr(root), name="image_text", rows=16),
        )

    # Vega-Lite specification.
    elif img["content_type"] == constants.JSON_CONTENT_TYPE:
        spec = json.loads(img["image"])
        fieldset = Fieldset(
            Legend("Vega-Lite"),
            Textarea(json.dumps(spec, indent=2), name="image_text", rows=16),
        )

    # PNG and JPEG formats.
    elif img["content_type"] in (
        constants.PNG_CONTENT_TYPE,
        constants.JPEG_CONTENT_TYPE,
    ):
        fieldset = (
            Fieldset(
                Legend(Tx("Image file")),
                Input(type="file", name="image_file", multiple=False),
            ),
        )

    title = Tx("Edit image")
    return (
        Title(title),
        components.header(request, title, book=get_imgs(), item=img),
        Main(
            Form(
                Fieldset(
                    Legend(Tx("Title")),
                    Input(name="title", value=img.title, autofocus=True),
                ),
                fieldset,
                Fieldset(
                    Legend(Tx("Caption")),
                    Textarea(img.content or "", name="caption"),
                ),
                Fieldset(
                    Legend(Tx("Status")),
                    components.get_status_field(img),
                ),
                components.save_button("Save image"),
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
            img.set("image", repr(root))
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
            img.set("image", json.dumps(spec))
            # Set caption from Vega-Lite description, if not set.
            if not caption:
                caption = spec.get("description")

    # PNG and JPEG formats.
    elif img["content_type"] in (
        constants.PNG_CONTENT_TYPE,
        constants.JPEG_CONTENT_TYPE,
    ):
        if image_file and image_file.size != 0:
            # Allow changing between PNG and JPEG formats.
            image_content = await image_file.read()
            img.set("content_type", image_file.content_type)
            img.set("image", base64.standard_b64encode(image_content).decode("utf-8"))
            img.set("base64", True)

    else:
        return Error(f"invalid image file content type '{image_file.content_type}'")

    # Caption may have been set from image contents.
    img.title = title or img["id"]
    img.write(content=caption)
    if status:
        img.status = status

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
    Returns a tuple of the generated SVG and the JSON specification.
    """
    try:
        spec = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(str(error))
    return (vl_convert.vegalite_to_svg(spec), spec)
