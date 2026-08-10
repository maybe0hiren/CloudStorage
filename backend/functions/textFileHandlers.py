import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import database.dbHandlers as dbHandlers


def getFilePath(UID: str, fileExt: str):
    storage = Path(os.getenv("STORAGE", "storage/"))
    if not storage.is_absolute():
        storage = Path(__file__).resolve().parents[1] / storage

    return str(storage / f"{UID}.{fileExt.lstrip('.')}")


def readFile(UID: str, fileExt: str):
    filePath = getFilePath(UID, fileExt)

    with open(filePath, "r", encoding="utf-8") as file:
        return file.read()


def writeFile(UID: str, fileExt: str, content: str):
    filePath = Path(getFilePath(UID, fileExt))
    filePath.parent.mkdir(parents=True, exist_ok=True)

    with open(filePath, "w", encoding="utf-8") as file:
        file.write(content)

    dbHandlers.updateLastEdited(UID)
    return 0


def saveToDisk(UID: str, fileExt: str):
    filePath = Path(getFilePath(UID, fileExt))
    filePath.parent.mkdir(parents=True, exist_ok=True)
    filePath.touch(exist_ok=True)
    return 0
