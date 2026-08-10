import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

load_dotenv()

import database.dbHandlers as dbHandlers


BASE_PATH = Path(__file__).resolve().parents[1]


def getStoragePath():
    storage = Path(os.getenv("STORAGE", "storage/"))

    if not storage.is_absolute():
        storage = BASE_PATH / storage

    return storage.resolve()


def getFilePath(UID: str, fileExt: str):
    return getStoragePath() / f"{UID}.{fileExt.lstrip('.')}"


def readFile(UID: str, fileExt: str):
    filePath = getFilePath(UID, fileExt)

    with filePath.open("r", encoding="utf-8") as file:
        return file.read()


def writeFile(UID: str, fileExt: str, content: str):
    filePath = getFilePath(UID, fileExt)
    filePath.parent.mkdir(parents=True, exist_ok=True)

    fd, tempName = tempfile.mkstemp(
        prefix=f".{UID}.",
        suffix=".tmp",
        dir=str(filePath.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(tempName, filePath)

        if dbHandlers.updateLastEdited(UID) != 0:
            return -1

        return 0
    except Exception as e:
        print(f"Failed to write text file: {e}")
        try:
            os.unlink(tempName)
        except FileNotFoundError:
            pass
        return -1


def saveToDisk(UID: str, fileExt: str):
    filePath = getFilePath(UID, fileExt)
    filePath.parent.mkdir(parents=True, exist_ok=True)

    if filePath.exists():
        return -1

    fd, tempName = tempfile.mkstemp(
        prefix=f".{UID}.",
        suffix=f".{fileExt.lstrip('.')}.tmp",
        dir=str(filePath.parent),
    )

    try:
        os.close(fd)
        os.replace(tempName, filePath)
        return 0
    except Exception as e:
        print(f"Failed to create text file: {e}")
        try:
            os.unlink(tempName)
        except FileNotFoundError:
            pass
        return -1
