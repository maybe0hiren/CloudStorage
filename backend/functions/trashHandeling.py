import database.dbHandlers as dbHandlers


def trash(UID: str):
    return dbHandlers.moveToTrash(UID)


def restore(UID: str):
    lastLoc = dbHandlers.getTrashLocation(UID)
    if lastLoc is None:
        return -1

    file = dbHandlers.getFile(UID)
    if file is None:
        return -1

    newUID = dbHandlers.restoreFromTrash(
        UID,
        lastLoc,
        file["FileName"],
    )

    return newUID if newUID is not None else -1
