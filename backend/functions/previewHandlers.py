import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def getPreview(uniqueID: str, fileName: str, fileFormat: str):
    """Return the preview path for a file.

    Preview generation is intentionally kept separate from database handling.
    The backend currently returns None for formats that do not have a preview
    implementation yet. The frontend can still use the original file endpoint.
    """

    previewFormats = {
        "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
    }

    if fileFormat.lower() not in previewFormats:
        return None

    previewStorage = Path(os.getenv("PREVIEW_STORAGE", "preview/"))
    if not previewStorage.is_absolute():
        previewStorage = Path(__file__).resolve().parents[1] / previewStorage

    previewPath = str(previewStorage / (uniqueID + "." + fileFormat.lower()))

    if os.path.exists(previewPath):
        return previewPath

    return None
