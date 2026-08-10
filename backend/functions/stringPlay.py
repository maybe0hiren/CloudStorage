import hashlib


def makeUID(filePath: str, fileName: str):
    value = f"{filePath}{fileName}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def encodeUID(UID: str):
    reverseUID = list(UID[::-1])

    for i in range(0, len(reverseUID) - 1, 2):
        reverseUID[i], reverseUID[i + 1] = (
            reverseUID[i + 1],
            reverseUID[i],
        )

    return "".join(reverseUID)


def decodeUID(encoded: str):
    if not encoded:
        return None

    scrambled = list(encoded)

    for i in range(0, len(scrambled) - 1, 2):
        scrambled[i], scrambled[i + 1] = (
            scrambled[i + 1],
            scrambled[i],
        )

    return "".join(scrambled)[::-1]


def makeLink(UID: str, sharingEndpoint: str):
    return (
        sharingEndpoint.rstrip("/")
        + "/"
        + encodeUID(UID)
        + ".file"
    )


def decodeLink(link: str, sharingEndpoint: str):
    prefix = sharingEndpoint.rstrip("/") + "/"

    if not link.startswith(prefix) or not link.endswith(".file"):
        return None

    encoded = link[len(prefix):-len(".file")]
    return decodeUID(encoded)
