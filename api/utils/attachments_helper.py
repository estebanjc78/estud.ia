# api/utils/attachments_helper.py

from models import Attachment


def serialize_attachment(attachment: Attachment) -> dict:
    return {
        "id": attachment.id,
        "context_type": attachment.context_type,
        "context_id": attachment.context_id,
        "kind": attachment.kind,
        "filename": attachment.filename,
        "storage_path": attachment.storage_path,
        "mime_type": attachment.mime_type,
        "file_size": attachment.file_size,
        "uploaded_by_profile_id": attachment.uploaded_by_profile_id,
        "visibility": attachment.visibility,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
    }
