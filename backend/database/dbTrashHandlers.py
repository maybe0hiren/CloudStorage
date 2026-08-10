import sqlite3
from datetime import datetime, timedelta
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


DB_NAME = os.getenv("DATABASE_PATH", "database/database.db")


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
            CREATE TABLE IF NOT EXISTS Trash (
                UID TEXT PRIMARY KEY,
                LastLoc TEXT NOT NULL,
                TrashedDate TEXT NOT NULL
            )
        """)

        conn.commit()
        return 0

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to create trash table: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def getValue(uid: str, column: str):
    allowed_columns = {"UID", "LastLoc", "TrashedDate"}

    if column not in allowed_columns:
        raise ValueError(f"Invalid column name: {column}")

    conn = None

    try:
        conn = getConnection()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT {column}
            FROM Trash
            WHERE UID = ?
        """, (uid,))

        row = cursor.fetchone()
        return row[0] if row else None

    except sqlite3.Error as e:
        print(f"Failed to get trash value: {e}")
        return None

    finally:
        if conn:
            conn.close()


def getTrash():
    conn = None

    try:
        conn = getConnection()
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute("""
            SELECT UID, LastLoc, TrashedDate
            FROM Trash
            ORDER BY TrashedDate DESC
        """)

        return [
            {
                "UID": row[0],
                "LastLoc": row[1],
                "TrashedDate": row[2],
            }
            for row in cursor.fetchall()
        ]

    except sqlite3.Error as e:
        print(f"Failed to get trash: {e}")
        return []

    finally:
        if conn:
            conn.close()


def trashHandeling(uid: str, lastLoc: str):
    conn = None

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = getConnection()
        if conn is None:
            return -1

        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO Trash
            (UID, LastLoc, TrashedDate)
            VALUES (?, ?, ?)
        """, (uid, lastLoc, today))

        conn.commit()
        return 0

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to handle trash: {e}")
        return -1

    finally:
        if conn:
            conn.close()


def restoreHandeling(uid: str):
    conn = None

    try:
        conn = getConnection()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute("""
            SELECT LastLoc
            FROM Trash
            WHERE UID = ?
        """, (uid,))

        row = cursor.fetchone()
        if row is None:
            return None

        lastLoc = row[0]

        cursor.execute("""
            DELETE FROM Trash
            WHERE UID = ?
        """, (uid,))

        conn.commit()
        return lastLoc

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to handle restore: {e}")
        return None

    finally:
        if conn:
            conn.close()


def clearing(UID=None):
    conn = None

    try:
        conn = getConnection()
        if conn is None:
            return -1

        cursor = conn.cursor()

        if UID is None:
            cutoffDate = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            cursor.execute("""
                DELETE FROM Trash
                WHERE TrashedDate < ?
            """, (cutoffDate,))
        else:
            cursor.execute("""
                DELETE FROM Trash
                WHERE UID = ?
            """, (UID,))

        conn.commit()
        return 0

    except sqlite3.Error as e:
        if conn:
            conn.rollback()

        print(f"Failed to clear trash: {e}")
        return -1

    finally:
        if conn:
            conn.close()


makeTable()
