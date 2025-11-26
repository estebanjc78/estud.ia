# api/utils/messages_helper.py
from models import Message

def serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_profile_id": msg.sender_profile_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }