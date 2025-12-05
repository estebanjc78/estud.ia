from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def save_logo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None
    ext = Path(filename).suffix
    storage_dir = Path(current_app.instance_path) / "uploads" / "logos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    final_name = f"{uuid4().hex}{ext}"
    file_path = storage_dir / final_name
    file_storage.save(file_path)
    return f"/uploads/logos/{final_name}"
