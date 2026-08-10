import database.dbHandlers as dbHandlers


def makeTable():
    # Trash is stored in the same SQLite database as Files.
    # dbHandlers.makeTable() creates both tables.
    return dbHandlers.makeTable()


def getConnection():
    return dbHandlers.getConnection()


def getValue(uid, column):
    if column not in {"UID", "LastLoc", "TrashedDate"}:
        raise ValueError(f"Invalid column name: {column}")

    conn = getConnection()
    if conn is None:
        return None

    try:
        row = conn.execute(
            f"SELECT {column} FROM Trash WHERE UID = ?",
            (uid,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def getTrash():
    return dbHandlers.getTrash()


def trashHandeling(uid, lastLoc):
    # Kept for compatibility with older callers.
    return dbHandlers.moveToTrash(uid)


def restoreHandeling(uid):
    return dbHandlers.getTrashLocation(uid)


def clearing(UID=None):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        if UID is None:
            conn.execute("""
                DELETE FROM Trash
                WHERE UID IN (
                    SELECT UID FROM Files
                    WHERE FilePath != 'Trash/'
                )
            """)
        else:
            conn.execute("DELETE FROM Trash WHERE UID = ?", (UID,))

        conn.commit()
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Failed to clear trash: {e}")
        return -1
    finally:
        conn.close()
