import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_PATH = Path(__file__).resolve().parents[1]
DB_NAME = os.getenv("DATABASE_PATH", "database/database.db")

ALLOWED_COLUMNS = {
    "UniqueID",
    "FileName",
    "FilePath",
    "LastEdited",
    "Format",
    "PreviewPath",
    "Link",
    "Encryption",
    "Size",
    "SHA256",
    "CreatedAt",
}


def getDatabasePath():
    databasePath = Path(DB_NAME)
    if not databasePath.is_absolute():
        databasePath = BASE_PATH / databasePath

    databasePath.parent.mkdir(parents=True, exist_ok=True)
    return databasePath.resolve()


def getConnection():
    try:
        conn = sqlite3.connect(
            str(getDatabasePath()),
            timeout=30,
            isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    except sqlite3.Error as e:
        print(f"Failed to connect to database: {e}")
        return None


def makeTable():
    conn = getConnection()
    if conn is None:
        return -1

    try:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS Files (
                UniqueID TEXT PRIMARY KEY,
                FileName TEXT NOT NULL,
                FilePath TEXT NOT NULL,
                LastEdited TEXT NOT NULL,
                Format TEXT,
                PreviewPath TEXT,
                Link TEXT,
                Encryption TEXT,
                Size INTEGER NOT NULL DEFAULT 0,
                SHA256 TEXT,
                CreatedAt TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS Trash (
                UID TEXT PRIMARY KEY,
                LastLoc TEXT NOT NULL,
                TrashedDate TEXT NOT NULL
            )
        """)

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(Files)").fetchall()
        }

        migrations = {
            "Encryption": "ALTER TABLE Files ADD COLUMN Encryption TEXT",
            "Size": "ALTER TABLE Files ADD COLUMN Size INTEGER NOT NULL DEFAULT 0",
            "SHA256": "ALTER TABLE Files ADD COLUMN SHA256 TEXT",
            "CreatedAt": "ALTER TABLE Files ADD COLUMN CreatedAt TEXT",
        }

        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_path
            ON Files(FilePath)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_name_path
            ON Files(FilePath, FileName)
        """)

        conn.commit()
        return 0

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to create database table: {e}")
        return -1
    finally:
        conn.close()


def _rowToDict(row):
    if row is None:
        return None

    return {
        "UniqueID": row[0],
        "FileName": row[1],
        "FilePath": row[2],
        "LastEdited": row[3],
        "Format": row[4],
        "PreviewPath": row[5],
        "Link": row[6],
        "Encryption": row[7],
        "Size": row[8],
        "SHA256": row[9],
        "CreatedAt": row[10],
    }


def getFile(uniqueID):
    conn = getConnection()
    if conn is None:
        return None

    try:
        row = conn.execute("""
            SELECT UniqueID, FileName, FilePath, LastEdited,
                   Format, PreviewPath, Link, Encryption,
                   Size, SHA256, CreatedAt
            FROM Files
            WHERE UniqueID = ?
        """, (uniqueID,)).fetchone()

        return _rowToDict(row)
    except sqlite3.Error as e:
        print(f"Failed to get file: {e}")
        return None
    finally:
        conn.close()


def getID(filePath, fileName):
    conn = getConnection()
    if conn is None:
        return None

    try:
        row = conn.execute("""
            SELECT UniqueID
            FROM Files
            WHERE FilePath = ? AND FileName = ?
            LIMIT 1
        """, (filePath, fileName)).fetchone()

        return row[0] if row else None
    except sqlite3.Error as e:
        print(f"Failed to get ID: {e}")
        return None
    finally:
        conn.close()


def getValue(uniqueID, column):
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column name: {column}")

    conn = getConnection()
    if conn is None:
        return None

    try:
        row = conn.execute(
            f"SELECT {column} FROM Files WHERE UniqueID = ?",
            (uniqueID,),
        ).fetchone()

        return row[0] if row else None
    except sqlite3.Error as e:
        print(f"Failed to get value: {e}")
        return None
    finally:
        conn.close()


def getFiles(filePath=None, includeTrash=False):
    conn = getConnection()
    if conn is None:
        return []

    try:
        query = """
            SELECT UniqueID, FileName, FilePath, LastEdited,
                   Format, PreviewPath, Link, Encryption,
                   Size, SHA256, CreatedAt
            FROM Files
        """
        values = []
        conditions = []

        if filePath is not None:
            conditions.append("FilePath = ?")
            values.append(filePath)

        if not includeTrash:
            conditions.append("FilePath != ?")
            values.append("Trash/")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY FilePath, FileName"

        rows = conn.execute(query, values).fetchall()
        return [_rowToDict(row) for row in rows]

    except sqlite3.Error as e:
        print(f"Failed to get files: {e}")
        return []
    finally:
        conn.close()


def addFile(
    filePath,
    fileName,
    encryption="none",
    uniqueID=None,
    size=0,
    sha256=None,
):
    if uniqueID is None:
        from functions.stringPlay import makeUID
        uniqueID = makeUID(filePath, fileName)

    fileFormat = Path(fileName).suffix.lstrip(".").lower() or "bin"

    try:
        from functions.previewHandlers import getPreview
        previewPath = getPreview(uniqueID, fileName, fileFormat)
    except Exception as e:
        print(f"Preview lookup failed: {e}")
        previewPath = None

    now = datetime.now().isoformat(timespec="seconds")
    conn = getConnection()
    if conn is None:
        return None

    try:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            INSERT INTO Files (
                UniqueID, FileName, FilePath, LastEdited,
                Format, PreviewPath, Link, Encryption,
                Size, SHA256, CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uniqueID,
            fileName,
            filePath,
            now,
            fileFormat,
            previewPath,
            None,
            encryption or "none",
            int(size),
            sha256,
            now,
        ))

        conn.commit()
        return uniqueID

    except sqlite3.IntegrityError:
        conn.rollback()
        print("A file with the same UniqueID already exists")
        return None
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to add file: {e}")
        return None
    finally:
        conn.close()


def updateFileMetadata(uniqueID, size, sha256):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = conn.execute("""
            UPDATE Files
            SET Size = ?, SHA256 = ?, LastEdited = ?
            WHERE UniqueID = ?
        """, (int(size), sha256, now, uniqueID))

        conn.commit()
        return 0 if cursor.rowcount else -1
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to update metadata: {e}")
        return -1
    finally:
        conn.close()


def setLink(uniqueID, link):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        cursor = conn.execute(
            "UPDATE Files SET Link = ? WHERE UniqueID = ?",
            (link, uniqueID),
        )
        conn.commit()
        return 0 if cursor.rowcount else -1
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to set link: {e}")
        return -1
    finally:
        conn.close()


def makeLink(uniqueID):
    return getValue(uniqueID, "Link")


def updateLastEdited(uniqueID):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = conn.execute(
            "UPDATE Files SET LastEdited = ? WHERE UniqueID = ?",
            (now, uniqueID),
        )
        conn.commit()
        return 0 if cursor.rowcount else -1
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to update LastEdited: {e}")
        return -1
    finally:
        conn.close()


def editPath(uniqueID, newPath, newName):
    from functions.stringPlay import makeUID

    oldFile = getFile(uniqueID)
    if oldFile is None:
        return None

    newUID = makeUID(newPath, newName)

    conn = getConnection()
    if conn is None:
        return None

    try:
        conn.execute("BEGIN IMMEDIATE")

        if newUID != uniqueID:
            existing = conn.execute(
                "SELECT 1 FROM Files WHERE UniqueID = ?",
                (newUID,),
            ).fetchone()
            if existing:
                conn.rollback()
                return None

        newFormat = Path(newName).suffix.lstrip(".").lower() or oldFile["Format"]
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute("""
            UPDATE Files
            SET UniqueID = ?,
                FileName = ?,
                FilePath = ?,
                Format = ?,
                PreviewPath = NULL,
                Link = NULL,
                LastEdited = ?
            WHERE UniqueID = ?
        """, (
            newUID,
            newName,
            newPath,
            newFormat,
            now,
            uniqueID,
        ))

        conn.commit()
        return newUID

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to edit path: {e}")
        return None
    finally:
        conn.close()


def moveToTrash(uniqueID):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT FilePath, FileName
            FROM Files
            WHERE UniqueID = ?
        """, (uniqueID,)).fetchone()

        if row is None:
            conn.rollback()
            return -1

        if row[0] == "Trash/":
            conn.commit()
            return 0

        lastLoc = row[0]
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute("""
            INSERT INTO Trash (UID, LastLoc, TrashedDate)
            VALUES (?, ?, ?)
            ON CONFLICT(UID) DO UPDATE SET
                LastLoc = excluded.LastLoc,
                TrashedDate = excluded.TrashedDate
        """, (uniqueID, lastLoc, now))

        conn.execute("""
            UPDATE Files
            SET FilePath = 'Trash/',
                Link = NULL,
                LastEdited = ?
            WHERE UniqueID = ?
        """, (now, uniqueID))

        conn.commit()
        return 0

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to move file to trash: {e}")
        return -1
    finally:
        conn.close()


def restoreFromTrash(uniqueID, newPath, newName):
    from functions.stringPlay import makeUID

    newUID = makeUID(newPath, newName)
    conn = getConnection()
    if conn is None:
        return None

    try:
        conn.execute("BEGIN IMMEDIATE")

        fileRow = conn.execute("""
            SELECT FileName, Format
            FROM Files
            WHERE UniqueID = ? AND FilePath = 'Trash/'
        """, (uniqueID,)).fetchone()

        trashRow = conn.execute("""
            SELECT LastLoc
            FROM Trash
            WHERE UID = ?
        """, (uniqueID,)).fetchone()

        if fileRow is None or trashRow is None:
            conn.rollback()
            return None

        if newUID != uniqueID:
            existing = conn.execute(
                "SELECT 1 FROM Files WHERE UniqueID = ?",
                (newUID,),
            ).fetchone()
            if existing:
                conn.rollback()
                return None

        newFormat = Path(newName).suffix.lstrip(".").lower() or fileRow[1]
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute("""
            UPDATE Files
            SET UniqueID = ?,
                FileName = ?,
                FilePath = ?,
                Format = ?,
                PreviewPath = NULL,
                Link = NULL,
                LastEdited = ?
            WHERE UniqueID = ?
        """, (newUID, newName, newPath, newFormat, now, uniqueID))

        conn.execute("DELETE FROM Trash WHERE UID = ?", (uniqueID,))

        conn.commit()
        return newUID

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to restore file: {e}")
        return None
    finally:
        conn.close()


def permanentlyDelete(uniqueID):
    conn = getConnection()
    if conn is None:
        return -1

    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT 1 FROM Files
            WHERE UniqueID = ? AND FilePath = 'Trash/'
        """, (uniqueID,)).fetchone()

        if row is None:
            conn.rollback()
            return -1

        conn.execute("DELETE FROM Trash WHERE UID = ?", (uniqueID,))
        conn.execute("DELETE FROM Files WHERE UniqueID = ?", (uniqueID,))

        conn.commit()
        return 0

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Failed to permanently delete file: {e}")
        return -1
    finally:
        conn.close()


def getTrash():
    conn = getConnection()
    if conn is None:
        return []

    try:
        rows = conn.execute("""
            SELECT UID, LastLoc, TrashedDate
            FROM Trash
            ORDER BY TrashedDate DESC
        """).fetchall()

        return [
            {"UID": row[0], "LastLoc": row[1], "TrashedDate": row[2]}
            for row in rows
        ]
    except sqlite3.Error as e:
        print(f"Failed to get trash: {e}")
        return []
    finally:
        conn.close()


def getTrashLocation(uniqueID):
    conn = getConnection()
    if conn is None:
        return None

    try:
        row = conn.execute(
            "SELECT LastLoc FROM Trash WHERE UID = ?",
            (uniqueID,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        print(f"Failed to get trash location: {e}")
        return None
    finally:
        conn.close()


def pathExists(filePath):
    conn = getConnection()
    if conn is None:
        return False

    try:
        row = conn.execute("""
            SELECT 1
            FROM Files
            WHERE FilePath = ? AND FilePath != 'Trash/'
            LIMIT 1
        """, (filePath,)).fetchone()
        return row is not None
    except sqlite3.Error as e:
        print(f"Failed to check path: {e}")
        return False
    finally:
        conn.close()


makeTable()
