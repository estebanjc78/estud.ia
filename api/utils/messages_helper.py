# api/utils/messages_helper.py
from models import Message
from api.utils.attachments_helper import serialize_attachment


def serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "thread_subject": msg.thread.subject if msg.thread else None,
        "sender_profile_id": msg.sender_profile_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "visible_for_student": msg.visible_for_student,
        "visible_for_parent": msg.visible_for_parent,
        "visible_for_teacher": msg.visible_for_teacher,
        "attachments": [serialize_attachment(att) for att in (msg.attachments or [])],
    }
