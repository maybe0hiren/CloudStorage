import database.dbTrashHandlers as dbTrashHandlers
import database.dbHandlers as dbHandlers


def trash(UID: str):
    file = dbHandlers.getFile(UID)
    if file is None:
        return -1

    if file["FilePath"] == "Trash/":
        return 0

    lastLoc = file["FilePath"]

    status = dbHandlers.deleteFile(UID)
    if status != 0:
        return -1

    status = dbTrashHandlers.trashHandeling(UID, lastLoc)
    if status != 0:
        # Best effort rollback of the logical path.
        dbHandlers.editPath(UID, lastLoc, file["FileName"])
        return -1

    return 0


def restore(UID: str):
    file = dbHandlers.getFile(UID)
    if file is None:
        return -1

    lastLoc = dbTrashHandlers.getValue(UID, "LastLoc")
    if lastLoc is None:
        return -1

    fileName = file["FileName"]
    newUID = dbHandlers.editPath(UID, lastLoc, fileName)

    if newUID is None:
        return -1

    status = dbTrashHandlers.clearing(UID)
    if status != 0:
        return -1

    return newUID
