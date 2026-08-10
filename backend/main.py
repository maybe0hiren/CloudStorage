import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from werkzeug.utils import secure_filename

load_dotenv()

import database.dbHandlers as dbHandlers
import database.dbTrashHandlers as dbTrashHandlers
import functions.stringPlay as stringPlay
import functions.textFileHandlers as textFileHandlers
import functions.trashHandeling as trashHandeling


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(100 * 1024 * 1024)))

BASE_PATH = Path(__file__).resolve().parent
STORAGE = Path(os.getenv("STORAGE", "storage/"))
PREVIEW_STORAGE = Path(os.getenv("PREVIEW_STORAGE", "preview/"))

if not STORAGE.is_absolute():
    STORAGE = BASE_PATH / STORAGE
if not PREVIEW_STORAGE.is_absolute():
    PREVIEW_STORAGE = BASE_PATH / PREVIEW_STORAGE

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
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024 * 1024)))


@app.after_request
def addCorsHeaders(response):
    # The frontend may be served from another device or development port.
    # This does not expose the storage itself; only the HTTP API is shared.
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Range"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges"
    return response


def initialise():
    STORAGE.mkdir(parents=True, exist_ok=True)
    PREVIEW_STORAGE.mkdir(parents=True, exist_ok=True)
    dbHandlers.makeTable()
    dbTrashHandlers.makeTable()


def normalisePath(filePath: str):
    if filePath is None:
        return None

    filePath = filePath.replace("\\", "/").strip()
    filePath = filePath.strip("/")

    if not filePath:
        return "home/"

    return filePath + "/"


def getPhysicalPath(UID: str, fileFormat: str):
    return STORAGE / f"{UID}.{fileFormat.lstrip('.') }"


def getFileRecord(UID: str):
    return dbHandlers.getFile(UID)


def createTextFile(fileName: str, filePath: str, content: str = ""):
    if not fileName or not filePath:
        return -1

    filePath = normalisePath(filePath)
    UID = stringPlay.makeUID(filePath, fileName)
    fileFormat = Path(fileName).suffix.lstrip(".").lower()

    if not fileFormat:
        return -1

    if dbHandlers.getFile(UID) is not None:
        return -1

    status = textFileHandlers.saveToDisk(UID, fileFormat)
    if status != 0:
        return -1

    status = textFileHandlers.writeFile(UID, fileFormat, content)
    if status != 0:
        return -1

    addedUID = dbHandlers.addFile(filePath, fileName, "none", UID)
    if addedUID is None:
        physicalPath = getPhysicalPath(UID, fileFormat)
        if physicalPath.exists():
            physicalPath.unlink()
        return -1

    return 0


def openFile(fileName: str, filePath: str):
    filePath = normalisePath(filePath)
    UID = dbHandlers.getID(filePath, fileName)

    if UID is None:
        return None

    fileFormat = dbHandlers.getValue(UID, "Format")
    if not fileFormat:
        return None

    physicalPath = getPhysicalPath(UID, fileFormat)
    if not physicalPath.exists():
        return None

    return physicalPath


def editTextFile(fileName: str, filePath: str, content: str):
    if not fileName or not filePath or content is None:
        return -1

    filePath = normalisePath(filePath)
    UID = dbHandlers.getID(filePath, fileName)

    if UID is None:
        return createTextFile(fileName, filePath, content)

    fileFormat = dbHandlers.getValue(UID, "Format")
    if not fileFormat:
        return -1

    return textFileHandlers.writeFile(UID, fileFormat, content)


def openImage(fileName: str, filePath: str):
    return openFile(fileName, filePath)


def openVideo(fileName: str, filePath: str):
    physicalPath = openFile(fileName, filePath)
    if physicalPath is None:
        return None, None

    UID = dbHandlers.getID(normalisePath(filePath), fileName)
    fileSize = physicalPath.stat().st_size
    totalChunks = (fileSize + CHUNK_SIZE - 1) // CHUNK_SIZE

    metadata = {
        "uid": UID,
        "fileName": fileName,
        "fileSize": fileSize,
        "chunkSize": CHUNK_SIZE,
        "totalChunks": totalChunks,
        "mimeType": mimetypes.guess_type(str(physicalPath))[0] or "application/octet-stream",
    }

    def chunkGenerator():
        with physicalPath.open("rb") as file:
            while True:
                chunk = file.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    return metadata, chunkGenerator()


def movePhysicalFile(oldUID: str, newUID: str, oldFormat: str, newFormat: str = None):
    if newFormat is None:
        newFormat = oldFormat

    oldPath = getPhysicalPath(oldUID, oldFormat)
    newPath = getPhysicalPath(newUID, newFormat)

    if oldPath == newPath:
        return True

    if not oldPath.exists():
        return False

    if newPath.exists():
        return False

    oldPath.rename(newPath)
    return True


def moveToTrash(fileName: str, filePath: str):
    filePath = normalisePath(filePath)
    UID = dbHandlers.getID(filePath, fileName)

    if UID is None:
        return -1

    return trashHandeling.trash(UID)


def deleteFromDisk(uniqueID: str):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return -1

    physicalPath = getPhysicalPath(uniqueID, file["Format"])
    if physicalPath.exists():
        physicalPath.unlink()

    dbTrashHandlers.clearing(uniqueID)
    return 0


def saveNewFile(file, filePath: str, encryption: str = "none"):
    if file is None or not file.filename:
        return None

    filePath = normalisePath(filePath)
    fileName = secure_filename(file.filename)

    if not fileName:
        return None

    UID = stringPlay.makeUID(filePath, fileName)

    if dbHandlers.getFile(UID) is not None:
        return None

    fileFormat = Path(fileName).suffix.lstrip(".").lower()
    if not fileFormat:
        fileFormat = "bin"

    fileOnDisk = getPhysicalPath(UID, fileFormat)
    file.save(fileOnDisk)

    if not fileOnDisk.exists():
        return None

    addedUID = dbHandlers.addFile(filePath, fileName, encryption, UID)
    if addedUID is None:
        fileOnDisk.unlink(missing_ok=True)
        return None

    return addedUID


def restoreFile(uniqueID: str):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return None

    lastLoc = dbTrashHandlers.getValue(uniqueID, "LastLoc")
    if lastLoc is None:
        return None

    oldUID = uniqueID
    oldFormat = file["Format"]
    oldName = file["FileName"]
    newUID = stringPlay.makeUID(lastLoc, oldName)

    if newUID != oldUID and dbHandlers.getFile(newUID) is not None:
        return None

    if not movePhysicalFile(oldUID, newUID, oldFormat, oldFormat):
        return None

    result = dbHandlers.editPath(oldUID, lastLoc, oldName)
    if result is None:
        movePhysicalFile(newUID, oldUID, oldFormat, oldFormat)
        return None

    dbTrashHandlers.clearing(oldUID)
    return result


def editFilePath(uniqueID: str, newPath: str, newName: str):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return None

    newPath = normalisePath(newPath)
    oldFormat = file["Format"]
    newFormat = Path(newName).suffix.lstrip(".").lower() or oldFormat

    newUID = stringPlay.makeUID(newPath, newName)

    if newUID != uniqueID and dbHandlers.getFile(newUID) is not None:
        return None

    if not movePhysicalFile(uniqueID, newUID, oldFormat, newFormat):
        return None

    result = dbHandlers.editPath(uniqueID, newPath, newName)
    if result is None:
        # Attempt to restore the physical filename.
        movePhysicalFile(newUID, uniqueID, newFormat, oldFormat)
        return None

    return result


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/files")
def listFiles():
    filePath = request.args.get("path")
    if filePath:
        filePath = normalisePath(filePath)

    return jsonify(dbHandlers.getFiles(filePath))


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

    if file is None:
        return jsonify({"error": "No file provided"}), 400

    UID = saveNewFile(file, filePath, encryption)
    if UID is None:
        return jsonify({"error": "Could not save file"}), 409

    return jsonify(dbHandlers.getFile(UID)), 201


@app.post("/api/files/text")
def createText():
    data = request.get_json(silent=True) or {}

    fileName = data.get("fileName")
    filePath = data.get("filePath", "home/")
    content = data.get("content", "")

    status = createTextFile(fileName, filePath, content)
    if status != 0:
        return jsonify({"error": "Could not create text file"}), 409

    UID = dbHandlers.getID(normalisePath(filePath), fileName)
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
        mimetype=mimetypes.guess_type(file["FileName"])[0] or "application/octet-stream",
    )


@app.get("/api/files/<uniqueID>/text")
def readText(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    if file["Format"].lower() not in TEXT_EXTENSIONS:
        return jsonify({"error": "File is not a text file"}), 400

    try:
        content = textFileHandlers.readFile(uniqueID, file["Format"])
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.put("/api/files/<uniqueID>/text")
def editText(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    if file["Format"].lower() not in TEXT_EXTENSIONS:
        return jsonify({"error": "File is not a text file"}), 400

    data = request.get_json(silent=True) or {}
    if "content" not in data:
        return jsonify({"error": "Content is required"}), 400

    status = textFileHandlers.writeFile(uniqueID, file["Format"], data["content"])
    if status != 0:
        return jsonify({"error": "Could not edit file"}), 500

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
    mimeType = mimetypes.guess_type(file["FileName"])[0] or "application/octet-stream"
    rangeHeader = request.headers.get("Range")

    if not rangeHeader:
        return send_file(physicalPath, mimetype=mimeType, conditional=True)

    try:
        rangeValue = rangeHeader.replace("bytes=", "")
        startText, endText = rangeValue.split("-", 1)
        start = int(startText) if startText else 0
        end = int(endText) if endText else fileSize - 1
        end = min(end, fileSize - 1)

        if start > end or start >= fileSize:
            return Response(status=416, headers={"Content-Range": f"bytes */{fileSize}"})

        length = end - start + 1

        def generate():
            with physicalPath.open("rb") as fileHandle:
                fileHandle.seek(start)
                remaining = length

                while remaining > 0:
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
        response.headers["Content-Range"] = f"bytes {start}-{end}/{fileSize}"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(length)
        return response

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid Range header"}), 416


@app.put("/api/files/<uniqueID>/path")
def editPath(uniqueID):
    data = request.get_json(silent=True) or {}
    newPath = data.get("newPath")
    newName = data.get("newName")

    if not newPath or not newName:
        return jsonify({"error": "newPath and newName are required"}), 400

    newUID = editFilePath(uniqueID, newPath, secure_filename(newName))
    if newUID is None:
        return jsonify({"error": "Could not move or rename file"}), 409

    return jsonify(dbHandlers.getFile(newUID))


@app.delete("/api/files/<uniqueID>")
def trashFile(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    status = trashHandeling.trash(uniqueID)
    if status != 0:
        return jsonify({"error": "Could not move file to trash"}), 500

    return jsonify({"status": "trashed", "UniqueID": uniqueID})


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
        return jsonify({"error": "Could not restore file"}), 409

    return jsonify(dbHandlers.getFile(newUID))


@app.delete("/api/trash/<uniqueID>")
def permanentlyDelete(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    if file["FilePath"] != "Trash/":
        return jsonify({"error": "File is not in trash"}), 400

    status = deleteFromDisk(uniqueID)
    if status != 0:
        return jsonify({"error": "Could not delete file"}), 500

    return jsonify({"status": "deleted", "UniqueID": uniqueID})


@app.get("/sharing/<encoded>.file")
def sharing(encoded):
    UID = stringPlay.decodeUID(encoded)

    if UID is None:
        return jsonify({"error": "Invalid sharing link"}), 400

    file = dbHandlers.getFile(UID)
    if file is None or file["FilePath"] == "Trash/":
        return jsonify({"error": "File not found"}), 404

    physicalPath = getPhysicalPath(UID, file["Format"])
    if not physicalPath.exists():
        return jsonify({"error": "File is missing from storage"}), 404

    return send_file(
        physicalPath,
        as_attachment=True,
        download_name=file["FileName"],
        mimetype=mimetypes.guess_type(file["FileName"])[0],
    )


@app.post("/api/files/<uniqueID>/link")
def createShareLink(uniqueID):
    file = dbHandlers.getFile(uniqueID)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    link = dbHandlers.makeLink(uniqueID)
    if link is None:
        sharingEndpoint = os.getenv("SHARING_ENDPOINT")
        if not sharingEndpoint:
            sharingEndpoint = request.host_url.rstrip("/") + "/sharing/"

        link = stringPlay.makeLink(uniqueID, sharingEndpoint)
        dbHandlers.setLink(uniqueID, link)

    return jsonify({"Link": link})


initialise()


if __name__ == "__main__":
    print(f"Overcast backend running on http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
