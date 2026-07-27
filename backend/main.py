import os
from pathlib import Path

from werkzeug.datastructures import FileStorage # gives usable file datatype
from werkzeug.utils import secure_filename # extracts name from path
import mimetypes

from dotenv import load_dotenv
load_dotenv()


import functions.textFileHandlers
import functions.stringPlay

import database.dbHandlers
import database.dbTrashHandlers

#-------------- Text -----------------------------

def createTextFile(fileName: str, filePath: str, content: str = None):
    print("creatTextFile() called")
    # safety check
    if not fileName or not filePath:
        return -1

    # get UID for the file
    UID = stringPlay.makeUID(filePath, fileName)

    # extract file format
    fileFormat = fileName.rsplit(".", 1)[-1]

    # Save file to disk
    status = textFileHandlers.saveToDisk(UID, fileFormat)
    if status != 0:
        return -1
    
    # write content to file
    if content != None:
        status = textFileHandlers.writeFile(UID, fileFormat, content)
        if status != 0:
            print("Error writing to file")
            return -1

    # add entry to main DB
    UID = dbHandlers.addFile(filePath, fileName, fileFormat, UID)
    if UID != -1:
        return 0

def openFile(fileName: str, filePath: str):
    print("openFile() called")

    # get UID for the file
    UID = dbHandlers.getID(filePath, fileName)
    if UID is None:
        print("Error getting UID")
        return -1

    # get the format
    fileFormat = dbHandlers.getValue(UID, "Format")
    if fileFormat in VIDEO_EXTENSIONS:
        # call openVideoFile()
        continue

    file = textFileHandlers.readFile(UID, fileFormat)
    return file

def editTextFile(fileName: str, filePath: str, content: str):
    # safety check
    if not fileName or not filePath or not content:
        print("Missing values")
        return -1
    
    # getUID
    UID = dbHandlers.getID(filePath, fileName)

    # get file format
    fileFormat = dbHandlers.getValue(UID, "Format")
    # create the file if it doesn not exist
    if UID == None:
        status = createTextFile(fileName, filePath, content)
        if status != 0:
            print("Error creating file")
            return -1
    
    # write if file already exists
    status = textFileHandlers.writeFile(UID, fileFormat, content)
    if status != 0:
        print("Error writing to file")
        return -1
    
    return 0
    
#-------------- Image -----------------------------
def openImage(fileName: str, filePath: str):
    print("openImage() called")
    # get UID and format
    UID = dbHandlers.getID(filePath, fileName)
    fileFormat = dbHandlers.getValue(UID, "Format")
    if not UID or not fileFormat:
        print("Error: file does not exist")
        return -1

    # fetch the file and return
    file = Path(filePath) / f"{UID}.{fileFormat}"
    if not file.exists():
        print("Error: file nor on disk")
        return -1
    
    return file        

#-------------- Video -----------------------------
CHUNK_SIZE = 100 * 1024 * 1024  # 100 MB
def openVideo(fileName: str, filePath: str):
    print("openVideo() called")

    # Get UID and format
    UID = dbHandlers.getID(filePath, fileName)
    fileFormat = dbHandlers.getValue(UID, "Format")
    if not UID or not fileFormat:
        print("Error: file does not exist")
        return -1

    # Get video/audio from storage
    fullPath = Path(filePath) / f"{UID}.{fileFormat}"
    if not fullPath.exists():
        print("File does not exist.")
        return -1

    # Size checks for threshold
    fileSize = fullPath.stat().st_size
    totalChunks = (fileSize + CHUNK_SIZE - 1) // CHUNK_SIZE
    # Metadata for backend
    metadata = {
        "uid": uid,
        "fileName": fileName,
        "fileSize": fileSize,
        "chunkSize": CHUNK_SIZE,
        "totalChunks": totalChunks,
        "mimeType": mimetypes.guess_type(fullPath)[0],
    }

    def chunkGenerator():
        # Open video/audio (binary) files
        with fullPath.open("rb") as file:
            while True:
                # Create chuncks of 100 MB
                chunk = file.read(CHUNK_SIZE)
                if not chunk:
                    break
                # yeild returns the vlaues without stopping the functions
                yield chunk
    return metadata, chunkGenerator()

#-------------- Common -----------------------------

def moveToTrash(fileName: str, filePath: str): 
    print("moveToTrash() called")
    status = 0
    
    # generate the UID of the file
    UID = dbHandlers.getID(filePath, fileName)
    if UID is None:
        print("Error getting UID")
        return -1

    # chage the path in main database
    newUID = dbHandlers.editPath(UID, "trash/")
    if newUID is None:
        print ("Error mainDB")
        return -1

    # make entry in the trash DB
    status = dbTrashHandlers.trashHandeling(newUID, filePath)
    if status != 0:
        print ("Error trashDB")
        return -1

    return 0

def deleteFromDisk(fileName: str, filePath: str):
    print("deleteFromDisk() called")
    status = 0
    
    # get the UID
    UID = dbHandlers.getID(filePath, fileName)
    if UID is None:
        print("Error getting ID")
        return -1
    #get file format
    fileFormat = dbHandlers.getValue(UID,"Format")

    # get the file from storage
    fileOnDisk = UID + fileFormat
    storage = os.getenv("STORAGE")
    if not storage:
        print("Error: Storage missing")
        return -1

    # delete file from disk
    file = Path(storage)/fileOnDisk
    if not file.exists():
        print("Error: File missing in storage")
        return -1
    
    # Delete from disk
    file.unlink()
    status = file.exists()
    if status == True:
        print("Error deleting file")
        return -1

    # clear from trash DB
    status = dbTrashHandlers.clearing(UID)
    if status != 0:
        return -1
    
    return 0
    

def saveNewFile(file: FileStorage, filePath: str):
    # get storage location
    storage = os.getenv("STORAGE")
    if not storage:
        print("Error: storage not found")
        return -1

    # extract file name
    fileName = secure_filename(file.filename)
    if not fileName:
        print("File name missing")
        return -1
    
    # save file to disk
    fileToSave = storage / fileName
    file.save(fileToSave)
    fileOnDisk = Path(fileToSave)
    if not fileOnDisk.exists():
        print("Error saving the file")
        return -1
    
    # make entry in DB
    dbHandlers.addFile(filePath, fileOnDisk.stem, fileOnDisk.suffix)

    

