"API access to books."

import datetime
import os
from pathlib import Path
import tarfile

from fasthtml.common import *

import auth
import components
import constants
import utils


app, rt = components.get_fast_app()


@rt("/")
def get(request):
    "Return a JSON dictionary of items {name: modified} for all files."
    auth.allow_admin(request)

    sourcedir = Path(os.environ["WRITETHATBOOK_DIR"])
    result = {}
    for dirpath, dirnames, filenames in os.walk(sourcedir):
        dirpath = Path(dirpath)
        for filename in filenames:
            filepath = dirpath / filename
            dt = datetime.datetime.fromtimestamp(filepath.stat().st_mtime)
            result[str(filepath.relative_to(sourcedir))] = utils.str_datetime_iso(dt)

    return result


@rt("/download")
async def post(request):
    "Return a TGZ file of those files given in the request JSON data."
    auth.allow_admin(request)

    data = await request.json()
    buffer = io.BytesIO()
    sourcedir = Path(os.environ["WRITETHATBOOK_DIR"])
    with tarfile.open(fileobj=buffer, mode="w:gz") as tgzfile:
        for name in data["files"]:
            path = sourcedir / name
            try:
                tgzfile.add(path, arcname=str(path.relative_to(sourcedir)))
            except FileNotFoundError:
                pass
    return Response(
        content=buffer.getvalue(),
        media_type=constants.GZIP_MIMETYPE,
    )
