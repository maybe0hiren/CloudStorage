import hashlib
import os

from dotenv import load_dotenv
load_dotenv()


def makeUID(filePath: str, fileName: str):
    string = filePath + fileName
    return hashlib.sha256(string.encode()).hexdigest()[:20]


def encodeUID(UID: str):
    reverseUID = list(UID[::-1])

    for i in range(0, len(reverseUID) - 1, 2):
        reverseUID[i], reverseUID[i + 1] = reverseUID[i + 1], reverseUID[i]

    return "".join(reverseUID)


def makeLink(UID: str, sharingEndpoint: str = None):
    if sharingEndpoint is None:
        sharingEndpoint = os.getenv("SHARING_ENDPOINT") or "http://localhost:8000/sharing/"

    return sharingEndpoint.rstrip("/") + "/" + encodeUID(UID) + ".file"


def decodeUID(encoded: str):
    if not encoded:
        return None

    scrambled = list(encoded)

    for i in range(0, len(scrambled) - 1, 2):
        scrambled[i], scrambled[i + 1] = scrambled[i + 1], scrambled[i]

    return "".join(scrambled)[::-1]


def decodeLink(link: str):
    sharingEndpoint = os.getenv("SHARING_ENDPOINT") or "http://localhost:8000/sharing/"

    if not link.startswith(sharingEndpoint) or not link.endswith(".file"):
        return None

    encoded = link[len(sharingEndpoint):-len(".file")]
    return decodeUID(encoded)
