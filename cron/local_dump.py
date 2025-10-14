"Create a tar dump file of the local production directory."

import datetime
import os
from pathlib import Path
import sys
import tarfile

# This must be done before importing 'constants'.
from dotenv import load_dotenv

load_dotenv()

# Allow finding chaos modules.
sys.path.insert(0, str(Path(sys.path[0]).parent))

import constants


def dump(source_dir, target_dir):
    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    tarfilepath = target_dir / f"writethatbook_{datetime.date.today()}.tgz"

    with tarfile.open(tarfilepath, mode="w:gz") as outfile:
        for dirpath, dirnames, filenames in os.walk(source_dir):
            abspath = Path(dirpath)
            relpath = Path(dirpath).relative_to(source_dir)
            for filename in filenames:
                outfile.add(
                    abspath.joinpath(filename), arcname=relpath.joinpath(filename)
                )


if __name__ == "__main__":
    dump(os.environ["WRITETHATBOOK_DIR"], os.environ["WRITETHATBOOK_DUMP_DIR"])
