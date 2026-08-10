import sqlite3
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()


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
}


def getConnection():
    try:
        basePath = Path(__file__).resolve().parents[1]
        databasePath = Path(DB_NAME)
        if not databasePath.is_absolute():
            databasePath = basePath / databasePath
        databasePath = databasePath.resolve()
        databasePath.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(databasePath))

    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return None


def makeTable():
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return -1

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Files (
                UniqueID TEXT PRIMARY KEY,
                FileName TEXT NOT NULL,
                FilePath TEXT NOT NULL,
                LastEdited TEXT NOT NULL,
                Format TEXT,
                PreviewPath TEXT,
                Link TEXT,
                Encryption TEXT
            )
        """)

        # Keep databases made by the previous version compatible.
        cursor.execute("PRAGMA table_info(Files)")
        columns = {row[1] for row in cursor.fetchall()}

        if "Encryption" not in columns:
            cursor.execute("ALTER TABLE Files ADD COLUMN Encryption TEXT")

        conn.commit()
        return 0

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to create table: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def getID(filePath: str, fileName: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return None

        cursor = conn.cursor()

        cursor.execute("""
            SELECT UniqueID
            FROM Files
            WHERE FilePath = ? AND FileName = ?
        """, (filePath, fileName))

        result = cursor.fetchone()

        if result:
            return result[0]

        return None

    except sqlite3.Error as e:
        print(f"Failed to get ID: {e}")
        return None

    finally:
        if conn:
            conn.close()


def getValue(uniqueID: str, column: str):
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column name: {column}")

    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return None

        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT {column}
            FROM Files
            WHERE UniqueID = ?
        """, (uniqueID,))

        row = cursor.fetchone()

        return row[0] if row else None

    except sqlite3.Error as e:
        print(f"Failed to get value: {e}")
        return None

    finally:
        if conn:
            conn.close()


def getFile(uniqueID: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute("""
            SELECT UniqueID, FileName, FilePath, LastEdited,
                   Format, PreviewPath, Link, Encryption
            FROM Files
            WHERE UniqueID = ?
        """, (uniqueID,))

        row = cursor.fetchone()

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
        }

    except sqlite3.Error as e:
        print(f"Failed to get file: {e}")
        return None

    finally:
        if conn:
            conn.close()


def getFiles(filePath: str = None, includeTrash: bool = False):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return []

        cursor = conn.cursor()

        query = """
            SELECT UniqueID, FileName, FilePath, LastEdited,
                   Format, PreviewPath, Link, Encryption
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

        cursor.execute(query, values)
        rows = cursor.fetchall()

        return [
            {
                "UniqueID": row[0],
                "FileName": row[1],
                "FilePath": row[2],
                "LastEdited": row[3],
                "Format": row[4],
                "PreviewPath": row[5],
                "Link": row[6],
                "Encryption": row[7],
            }
            for row in rows
        ]

    except sqlite3.Error as e:
        print(f"Failed to get files: {e}")
        return []

    finally:
        if conn:
            conn.close()


def addFile(filePath: str, fileName: str, encryption: str = "none", uniqueID: str = None):
    conn = None

    try:
        if uniqueID is None:
            from functions.stringPlay import makeUID
            uniqueID = makeUID(filePath, fileName)

        fileFormat = os.path.splitext(fileName)[1].lstrip(".").lower()

        # getPreview() belongs to the preview handler. Keep this call here
        # so preview generation can be changed without changing the database.
        from functions.previewHandlers import getPreview
        previewPath = getPreview(uniqueID, fileName, fileFormat)

        lastEdited = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = getConnection()
        if conn is None:
            return None

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Files
            (UniqueID, FileName, FilePath, LastEdited, Format, PreviewPath, Link, Encryption)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uniqueID,
            fileName,
            filePath,
            lastEdited,
            fileFormat,
            previewPath,
            None,
            encryption,
        ))

        conn.commit()

        return uniqueID

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to add file: {e}")
        return None

    except Exception as e:
        if conn:
            conn.rollback()

        print(f"Failed to add file: {e}")
        return None

    finally:
        if conn:
            conn.close()


def deleteFile(uniqueID: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return -1

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Files
            SET FilePath = ?,
                LastEdited = ?
            WHERE UniqueID = ?
        """, ("Trash/", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uniqueID))

        conn.commit()

        return 0 if cursor.rowcount else -1

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to delete file: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def makeLink(uniqueID: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return None

        cursor = conn.cursor()

        cursor.execute("""
            SELECT Link
            FROM Files
            WHERE UniqueID = ?
        """, (uniqueID,))

        result = cursor.fetchone()

        return result[0] if result else None

    except sqlite3.Error as e:
        print(f"Failed to get link: {e}")
        return None

    finally:
        if conn:
            conn.close()


def setLink(uniqueID: str, link: str):
    conn = None

    try:
        conn = getConnection()
        if conn is None:
            return -1

        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Files
            SET Link = ?
            WHERE UniqueID = ?
        """, (link, uniqueID))

        conn.commit()
        return 0 if cursor.rowcount else -1

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to set link: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def editPath(uniqueID: str, newPath: str, newName: str = None):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return None

        oldFile = getFile(uniqueID)
        if oldFile is None:
            return None

        if newName is None:
            newName = oldFile["FileName"]

        newFormat = os.path.splitext(newName)[1].lstrip(".").lower()

        if not newFormat:
            newFormat = oldFile["Format"]

        if (
            newPath == oldFile["FilePath"]
            and newName == oldFile["FileName"]
        ):
            return uniqueID

        from functions.stringPlay import makeUID
        newUID = makeUID(newPath, newName)

        # Do not silently overwrite another file.
        existing = getFile(newUID)
        if existing is not None and newUID != uniqueID:
            print("A file already exists at the new location")
            return None

        lastEdited = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Files
            SET UniqueID = ?,
                FilePath = ?,
                FileName = ?,
                Format = ?,
                LastEdited = ?
            WHERE UniqueID = ?
        """, (
            newUID,
            newPath,
            newName,
            newFormat,
            lastEdited,
            uniqueID,
        ))

        conn.commit()

        return newUID

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to edit path: {e}")
        return None

    except Exception as e:
        if conn:
            conn.rollback()

        print(f"Failed to edit path: {e}")
        return None

    finally:
        if conn:
            conn.close()


def updateLastEdited(uniqueID: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return -1

        currTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Files
            SET LastEdited = ?
            WHERE UniqueID = ?
        """, (currTime, uniqueID))

        conn.commit()
        return 0 if cursor.rowcount else -1

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to update last edited: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def pathExists(filePath: str):
    conn = None

    try:
        conn = getConnection()

        if conn is None:
            return False

        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1
                FROM Files
                WHERE FilePath = ?
                  AND FilePath != ?
            )
        """, (filePath, "Trash/"))

        return bool(cursor.fetchone()[0])

    except sqlite3.Error as e:
        print(f"Failed to check path: {e}")
        return False

    finally:
        if conn:
            conn.close()


makeTable()
