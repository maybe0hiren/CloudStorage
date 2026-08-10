import hashlib
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_file,
    stream_with_context,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

load_dotenv()

import database.dbHandlers as dbHandlers
import database.dbTrashHandlers as dbTrashHandlers
import functions.stringPlay as stringPlay
import functions.textFileHandlers as textFileHandlers
import functions.trashHandeling as trashHandeling


HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(8 * 1024 * 1024)))
MAX_UPLOAD_SIZE = int(
    os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024 * 1024))
)

BASE_PATH = Path(__file__).resolve().parent


def getConfiguredPath(name, default):
    value = Path(os.getenv(name, default))

    if not value.is_absolute():
        value = BASE_PATH / value

    return value.resolve()


STORAGE = getConfiguredPath("STORAGE", "storage/")
PREVIEW_STORAGE = getConfiguredPath("PREVIEW_STORAGE", "preview/")
TEMP_STORAGE = getConfiguredPath("TEMP_STORAGE", "temp/")
DATABASE_PATH = dbHandlers.getDatabasePath()

TEXT_EXTENSIONS = {
    "txt", "md", "json", "xml", "csv", "log", "py", "js", "ts",
    "jsx", "tsx", "html", "css", "scss", "c", "cpp", "h", "hpp",
    "java", "kt", "rs", "go", "php", "rb", "sh", "yml", "yaml",
}

VIDEO_EXTENSIONS = {
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v",
    "mpeg", "mpg", "3gp",
}

IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


def initialise():
    STORAGE.mkdir(parents=True, exist_ok=True)
    PREVIEW_STORAGE.mkdir(parents=True, exist_ok=True)
    TEMP_STORAGE.mkdir(parents=True, exist_ok=True)

    if dbHandlers.makeTable() != 0:
        raise RuntimeError("Database initialization failed")


def normalisePath(filePath: str):
    if filePath is None:
        return None

    filePath = str(filePath).replace("\\", "/").strip()
    filePath = filePath.strip("/")

    if not filePath:
        return "home/"

    parts = [part for part in filePath.split("/") if part]

    if any(part in {".", ".."} for part in parts):
        raise ValueError("Invalid path")

    return "/".join(parts) + "/"


def getPhysicalPath(UID: str, fileFormat: str):
    safeFormat = (fileFormat or "bin").lstrip(".").lower()

    if not safeFormat.isalnum():
        raise ValueError("Invalid file format")

    return STORAGE / f"{UID}.{safeFormat}"


def getFileRecord(UID: str):
    return dbHandlers.getFile(UID)


def calculateSHA256(filePath):
    digest = hashlib.sha256()
    size = 0

    with Path(filePath).open("rb") as file:
        while True:
            chunk = file.read(CHUNK_SIZE)
            if not chunk:
                break

            digest.update(chunk)
            size += len(chunk)

    return size, digest.hexdigest()


def checkDiskSpace(requiredBytes=0):
    usage = shutil.disk_usage(STORAGE)

    # Keep at least 512 MiB free after an upload.
    minimumFree = 512 * 1024 * 1024

    return usage.free >= requiredBytes + minimumFree


def saveUploadedFile(file, filePath, encryption="none"):
    if file is None or not file.filename:
        return None

    fileName = secure_filename(file.filename)

    if not fileName:
        return None

    filePath = normalisePath(filePath)
    UID = stringPlay.makeUID(filePath, fileName)

    if dbHandlers.getFile(UID) is not None:
        return None

    fileFormat = Path(fileName).suffix.lstrip(".").lower() or "bin"
    finalPath = getPhysicalPath(UID, fileFormat)

    if finalPath.exists():
        return None

    # FileStorage.save() writes to disk rather than loading the complete
    # upload into RAM.
    tempFile = None

    try:
        if not checkDiskSpace():
            return None

        fd, tempName = tempfile.mkstemp(
            prefix=f".upload-{UID}-",
            suffix=".tmp",
            dir=str(TEMP_STORAGE),
        )
        os.close(fd)
        tempFile = Path(tempName)

        file.save(str(tempFile))

        if not tempFile.exists():
            return None

        size, sha256 = calculateSHA256(tempFile)

        if size > MAX_UPLOAD_SIZE:
            return None

        if not checkDiskSpace(size):
            return None

        # Atomic publish: a file is either absent or complete.
        os.replace(tempFile, finalPath)
        tempFile = None

        addedUID = dbHandlers.addFile(
            filePath,
            fileName,
            encryption,
            UID,
            size,
            sha256,
        )

        if addedUID is None:
            finalPath.unlink(missing_ok=True)
            return None

        return addedUID

    except Exception as e:
        print(f"Failed to save upload: {e}")

        if tempFile is not None:
            tempFile.unlink(missing_ok=True)

        finalPath.unlink(missing_ok=True)
        return None


def createTextFile(fileName, filePath, content=""):
    fileName = secure_filename(fileName or "")

    if not fileName or content is None:
        return -1

    try:
        filePath = normalisePath(filePath)
    except ValueError:
        return -1

    fileFormat = Path(fileName).suffix.lstrip(".").lower()

    if not fileFormat or fileFormat not in TEXT_EXTENSIONS:
        return -1

    UID = stringPlay.makeUID(filePath, fileName)

    if dbHandlers.getFile(UID) is not None:
        return -1

    if textFileHandlers.saveToDisk(UID, fileFormat) != 0:
        return -1

    if textFileHandlers.writeFile(UID, fileFormat, content) != 0:
        getPhysicalPath(UID, fileFormat).unlink(missing_ok=True)
        return -1

    size, sha256 = calculateSHA256(getPhysicalPath(UID, fileFormat))

    addedUID = dbHandlers.addFile(
        filePath,
        fileName,
        "none",
        UID,
        size,
        sha256,
    )

    if addedUID is None:
        getPhysicalPath(UID, fileFormat).unlink(missing_ok=True)
        return -1

    return 0


def movePhysicalFile(oldUID, newUID, oldFormat, newFormat=None):
    newFormat = newFormat or oldFormat

    oldPath = getPhysicalPath(oldUID, oldFormat)
    newPath = getPhysicalPath(newUID, newFormat)

    if oldPath == newPath:
        return True

    if not oldPath.exists() or newPath.exists():
        return False

    try:
        os.replace(oldPath, newPath)
        return True
    except OSError as e:
        print(f"Failed to move physical file: {e}")
        return False


def editFilePath(uniqueID, newPath, newName):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return None

    newName = secure_filename(newName or "")
    if not newName:
        return None

    try:
        newPath = normalisePath(newPath)
    except ValueError:
        return None

    newUID = stringPlay.makeUID(newPath, newName)

    if newUID != uniqueID and dbHandlers.getFile(newUID) is not None:
        return None

    oldFormat = file["Format"]
    newFormat = Path(newName).suffix.lstrip(".").lower() or oldFormat

    if not movePhysicalFile(
        uniqueID,
        newUID,
        oldFormat,
        newFormat,
    ):
        return None

    result = dbHandlers.editPath(uniqueID, newPath, newName)

    if result is None:
        movePhysicalFile(
            newUID,
            uniqueID,
            newFormat,
            oldFormat,
        )
        return None

    return result


def restoreFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None or file["FilePath"] != "Trash/":
        return None

    lastLoc = dbHandlers.getTrashLocation(uniqueID)

    if lastLoc is None:
        return None

    newUID = stringPlay.makeUID(lastLoc, file["FileName"])

    if newUID != uniqueID and dbHandlers.getFile(newUID) is not None:
        return None

    oldFormat = file["Format"]
    newFormat = Path(file["FileName"]).suffix.lstrip(".").lower() or oldFormat

    if not movePhysicalFile(
        uniqueID,
        newUID,
        oldFormat,
        newFormat,
    ):
        return None

    result = dbHandlers.restoreFromTrash(
        uniqueID,
        lastLoc,
        file["FileName"],
    )

    if result is None:
        movePhysicalFile(
            newUID,
            uniqueID,
            newFormat,
            oldFormat,
        )
        return None

    return result


@app.after_request
def addCorsHeaders(response):
    origin = request.headers.get("Origin")

    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Range"
    )
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, OPTIONS"
    )
    response.headers["Access-Control-Expose-Headers"] = (
        "Content-Length, Content-Range, Accept-Ranges"
    )

    return response


@app.errorhandler(RequestEntityTooLarge)
def uploadTooLarge(error):
    return jsonify({
        "error": "File exceeds the configured upload limit"
    }), 413


@app.errorhandler(Exception)
def handleUnexpectedError(error):
    print(f"Unhandled backend error: {error}")
    return jsonify({"error": "Internal server error"}), 500


@app.route("/api/<path:_path>", methods=["OPTIONS"])
def options(_path):
    return Response(status=204)


@app.get("/api/health")
def health():
    databaseOK = dbHandlers.makeTable() == 0
    storageOK = STORAGE.exists() and STORAGE.is_dir()

    return jsonify({
        "status": "ok" if databaseOK and storageOK else "degraded",
        "database": databaseOK,
        "storage": storageOK,
    })


@app.get("/api/storage")
def storageInfo():
    usage = shutil.disk_usage(STORAGE)

    return jsonify({
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
    })


@app.get("/api/files")
def listFiles():
    try:
        filePath = request.args.get("path")

        if filePath:
            filePath = normalisePath(filePath)

        return jsonify(dbHandlers.getFiles(filePath))

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/files/<uniqueID>")
def getFile(uniqueID):
    file = getFileRecord(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    return jsonify(file)


@app.post("/api/files/upload")
def uploadFile():
    file = request.files.get("file")
    filePath = request.form.get("path", "home/")
    encryption = request.form.get("encryption", "none")

    try:
        filePath = normalisePath(filePath)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if file is None:
        return jsonify({"error": "No file provided"}), 400

    UID = saveUploadedFile(file, filePath, encryption)

    if UID is None:
        return jsonify({"error": "Could not save file"}), 409

    return jsonify(dbHandlers.getFile(UID)), 201


@app.post("/api/files/text")
def createText():
    data = request.get_json(silent=True) or {}

    status = createTextFile(
        data.get("fileName"),
        data.get("filePath", "home/"),
        data.get("content", ""),
    )

    if status != 0:
        return jsonify({"error": "Could not create text file"}), 409

    UID = dbHandlers.getID(
        normalisePath(data.get("filePath", "home/")),
        secure_filename(data.get("fileName", "")),
    )

    return jsonify(dbHandlers.getFile(UID)), 201


@app.get("/api/files/<uniqueID>/download")
def downloadFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    physicalPath = getPhysicalPath(uniqueID, file["Format"])

    if not physicalPath.exists():
        return jsonify({"error": "File is missing from storage"}), 404

    return send_file(
        physicalPath,
        as_attachment=True,
        download_name=file["FileName"],
        mimetype=mimetypes.guess_type(file["FileName"])[0],
        conditional=True,
    )


@app.get("/api/files/<uniqueID>/preview")
def previewFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    physicalPath = getPhysicalPath(uniqueID, file["Format"])

    if not physicalPath.exists():
        return jsonify({"error": "File is missing from storage"}), 404

    return send_file(
        physicalPath,
        mimetype=mimetypes.guess_type(file["FileName"])[0]
        or "application/octet-stream",
        conditional=True,
    )


@app.get("/api/files/<uniqueID>/text")
def readText(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    if (file["Format"] or "").lower() not in TEXT_EXTENSIONS:
        return jsonify({"error": "File is not a text file"}), 400

    try:
        return jsonify({
            "content": textFileHandlers.readFile(
                uniqueID,
                file["Format"],
            )
        })
    except (OSError, UnicodeError):
        return jsonify({"error": "Could not read file"}), 500


@app.put("/api/files/<uniqueID>/text")
def editText(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    if (file["Format"] or "").lower() not in TEXT_EXTENSIONS:
        return jsonify({"error": "File is not a text file"}), 400

    data = request.get_json(silent=True) or {}

    if "content" not in data or not isinstance(data["content"], str):
        return jsonify({"error": "Content is required"}), 400

    if textFileHandlers.writeFile(
        uniqueID,
        file["Format"],
        data["content"],
    ) != 0:
        return jsonify({"error": "Could not edit file"}), 500

    physicalPath = getPhysicalPath(uniqueID, file["Format"])
    size, sha256 = calculateSHA256(physicalPath)
    dbHandlers.updateFileMetadata(uniqueID, size, sha256)

    return jsonify(dbHandlers.getFile(uniqueID))


@app.get("/api/files/<uniqueID>/stream")
def streamFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    physicalPath = getPhysicalPath(uniqueID, file["Format"])

    if not physicalPath.exists():
        return jsonify({"error": "File is missing from storage"}), 404

    fileSize = physicalPath.stat().st_size
    mimeType = (
        mimetypes.guess_type(file["FileName"])[0]
        or "application/octet-stream"
    )

    rangeHeader = request.headers.get("Range")

    if not rangeHeader:
        return send_file(
            physicalPath,
            mimetype=mimeType,
            conditional=True,
        )

    if not rangeHeader.startswith("bytes="):
        return Response(
            status=416,
            headers={"Content-Range": f"bytes */{fileSize}"},
        )

    try:
        value = rangeHeader[6:].split(",", 1)[0]
        startText, endText = value.split("-", 1)

        if startText:
            start = int(startText)
            end = int(endText) if endText else fileSize - 1
        else:
            suffixLength = int(endText)
            if suffixLength <= 0:
                raise ValueError
            start = max(fileSize - suffixLength, 0)
            end = fileSize - 1

        if start < 0 or start >= fileSize:
            raise ValueError

        end = min(end, fileSize - 1)

        if start > end:
            raise ValueError

    except (ValueError, TypeError):
        return Response(
            status=416,
            headers={"Content-Range": f"bytes */{fileSize}"},
        )

    length = end - start + 1

    def generate():
        with physicalPath.open("rb") as fileHandle:
            fileHandle.seek(start)
            remaining = length

            while remaining:
                chunk = fileHandle.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    response = Response(
        stream_with_context(generate()),
        status=206,
        mimetype=mimeType,
        direct_passthrough=True,
    )

    response.headers["Content-Range"] = (
        f"bytes {start}-{end}/{fileSize}"
    )
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Content-Length"] = str(length)

    return response


@app.put("/api/files/<uniqueID>/path")
def editPath(uniqueID):
    data = request.get_json(silent=True) or {}

    newPath = data.get("newPath")
    newName = data.get("newName")

    if not newPath or not newName:
        return jsonify({
            "error": "newPath and newName are required"
        }), 400

    result = editFilePath(uniqueID, newPath, newName)

    if result is None:
        return jsonify({
            "error": "Could not move or rename file"
        }), 409

    return jsonify(dbHandlers.getFile(result))


@app.delete("/api/files/<uniqueID>")
def trashFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    if trashHandeling.trash(uniqueID) != 0:
        return jsonify({
            "error": "Could not move file to trash"
        }), 500

    return jsonify({
        "status": "trashed",
        "UniqueID": uniqueID,
    })


@app.get("/api/trash")
def listTrash():
    trash = dbTrashHandlers.getTrash()
    files = []

    for item in trash:
        file = dbHandlers.getFile(item["UID"])

        if file is not None:
            file.update(item)
            files.append(file)

    return jsonify(files)


@app.post("/api/trash/<uniqueID>/restore")
def restoreTrash(uniqueID):
    newUID = restoreFile(uniqueID)

    if newUID is None:
        return jsonify({
            "error": "Could not restore file"
        }), 409

    return jsonify(dbHandlers.getFile(newUID))


@app.delete("/api/trash/<uniqueID>")
def permanentlyDelete(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None:
        return jsonify({"error": "File not found"}), 404

    if file["FilePath"] != "Trash/":
        return jsonify({
            "error": "File is not in trash"
        }), 400

    physicalPath = getPhysicalPath(
        uniqueID,
        file["Format"],
    )

    try:
        if physicalPath.exists():
            physicalPath.unlink()
    except OSError as e:
        print(f"Failed to delete physical file: {e}")
        return jsonify({
            "error": "Could not delete physical file"
        }), 500

    if dbHandlers.permanentlyDelete(uniqueID) != 0:
        return jsonify({
            "error": "Could not update database"
        }), 500

    return jsonify({
        "status": "deleted",
        "UniqueID": uniqueID,
    })


@app.post("/api/files/<uniqueID>/link")
def createShareLink(uniqueID):
    file = dbHandlers.getFile(uniqueID)

    if file is None or file["FilePath"] == "Trash/":
        return jsonify({"error": "File not found"}), 404

    link = dbHandlers.makeLink(uniqueID)

    if link is None:
        endpoint = os.getenv("SHARING_ENDPOINT", "").strip()

        if not endpoint:
            endpoint = request.host_url.rstrip("/") + "/sharing"

        link = stringPlay.makeLink(uniqueID, endpoint)

        if dbHandlers.setLink(uniqueID, link) != 0:
            return jsonify({
                "error": "Could not save share link"
            }), 500

    return jsonify({"Link": link})


@app.get("/sharing/<encoded>.file")
def sharing(encoded):
    UID = stringPlay.decodeUID(encoded)

    if UID is None:
        return jsonify({"error": "Invalid sharing link"}), 400

    file = dbHandlers.getFile(UID)

    if file is None or file["FilePath"] == "Trash/":
        return jsonify({"error": "File not found"}), 404

    physicalPath = getPhysicalPath(
        UID,
        file["Format"],
    )

    if not physicalPath.exists():
        return jsonify({
            "error": "File is missing from storage"
        }), 404

    return send_file(
        physicalPath,
        as_attachment=True,
        download_name=file["FileName"],
        mimetype=mimetypes.guess_type(file["FileName"])[0],
        conditional=True,
    )


initialise()


if __name__ == "__main__":
    print(f"Cloud Storage backend running on http://{HOST}:{PORT}")
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        threaded=True,
    )
