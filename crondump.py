"Fetch and save gzipped tar files from an instance."

import json
from pathlib import Path
import sys
import requests

import utils


def fetch_and_save(url, apikey, dirpath):
    "Fetch the gzipped tar file and save to local disk."

    print(f"fetching mdbook.tgz from {url}")
    response = requests.get(url, headers=dict(apikey=apikey))

    if response.status_code != 200:
        raise ValueError(f"invalid status code for response: {response.status_code}")
    try:
        content_disposition = response.headers["content-disposition"]
    except KeyError:
        raise ValueError("no content-disposition in response")
    parts = content_disposition.split('"')
    if len(parts) != 3:
        raise ValueError("no filename in content-disposition in response")

    filepath = dirpath.joinpath(parts[1])
    with filepath.open("wb") as outfile:
        outfile.write(response.content)
    print(f"wrote mdbook.tgz to {filepath}")


if __name__ == "__main__":
    dirpath = Path(sys.argv[1])
    with dirpath.joinpath("config.json").open() as infile:
        config = json.load(infile)
    fetch_and_save(config["site"].rstrip("/") + "/tgz", config["apikey"], dirpath)
