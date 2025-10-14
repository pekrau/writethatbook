"Synchronize remote data to local directory."

import datetime
from http import HTTPStatus as HTTP
import io
import json
import os
from pathlib import Path
import sys
import tarfile

import requests

# Allow finding writethatbook modules.
sys.path.insert(0, str(Path(sys.path[0]).parent))

# This must be done before importing 'constants'.
from dotenv import load_dotenv

load_dotenv()

import constants
import utils
from timer import Timer

timer = Timer()


def update(url, apikey):
    "Get the current list of remote files, compare and update the local files."

    response = requests.get(url.rstrip("/") + "/api/", headers=dict(apikey=apikey))
    if response.status_code in (HTTP.BAD_GATEWAY, HTTP.SERVICE_UNAVAILABLE):
        raise IOError(f"invalid response: {response.status_code=}")
    elif response.status_code != HTTP.OK:
        raise IOError(f"invalid response: {response.status_code=} {response.content=}")

    remote_files = response.json()

    local_files = {}
    sourcedir = Path(os.environ["WRITETHATBOOK_DIR"])
    for dirpath, dirnames, filenames in os.walk(sourcedir):
        dirpath = Path(dirpath)
        for filename in filenames:
            filepath = dirpath / filename
            dt = datetime.datetime.fromtimestamp(filepath.stat().st_mtime)
            local_files[str(filepath.relative_to(sourcedir))] = utils.str_datetime_iso(
                dt
            )

    download_files = set()
    for name, modified in remote_files.items():
        if (name not in local_files) or (local_files[name] != modified):
            download_files.add(name)

    if download_files:
        response = requests.post(
            url + "/api/download",
            json={"files": list(download_files)},
            headers=dict(apikey=apikey),
        )
        if response.status_code in (HTTP.BAD_GATEWAY, HTTP.SERVICE_UNAVAILABLE):
            raise IOError(f"invalid response: {response.status_code=}")
        elif response.status_code != HTTP.OK:
            raise IOError(
                f"invalid response: {response.status_code=} {response.content=}"
            )

        if response.headers["Content-Type"] != constants.GZIP_MIMETYPE:
            raise IOError("invalid file type from remote")

        content = response.content
        if not content:
            raise IOError("empty TGZ file from remote")
        try:
            tf = tarfile.open(fileobj=io.BytesIO(content), mode="r:gz")
            tf.extractall(path=os.environ["WRITETHATBOOK_DIR"])
        except tarfile.TarError as message:
            raise IOError(f"tar file error: {message}")

    # Delete local files that do not exist in the remote.
    delete_files = set(local_files.keys()).difference(remote_files.keys())
    for name in delete_files:
        path = sourcedir / name
        path.unlink()

    if not download_files and not delete_files:
        return {}
    else:
        result = {
            "local": len(local_files),
            "remote": len(remote_files),
            "downloaded": len(download_files),
            "deleted": len(delete_files),
            "time": str(timer),
        }
    return result


if __name__ == "__main__":
    url = os.environ["WRITETHATBOOK_REMOTE_URL"]
    print(f"writethatbook {timer.now}, instance {url}")
    result = update(url, os.environ["WRITETHATBOOK_APIKEY"])
    if result:
        print(", ".join([f"{k}={v}" for k, v in result.items()]))
