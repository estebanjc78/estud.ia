# api/services/message_logic.py

from typing import List, Dict

from api.services.messages_service import MessageService
from api.utils.messages_helper import serialize_message


class MessageLogic:
    """
    Capa de lógica de dominio sobre el servicio de mensajes.
    Se encarga de orquestar llamadas y devolver estructuras serializadas.
    """

    @staticmethod
    def send_message_and_serialize(
        context_type: str,
        context_id: int,
        sender_profile_id: int,
        text: str,
        participant_ids: List[int] | None = None,
    ) -> Dict:
        msg = MessageService.send_message_to_context(
            context_type=context_type,
            context_id=context_id,
            sender_profile_id=sender_profile_id,
            text=text,
            participant_ids=participant_ids,
        )
        return serialize_message(msg)

    @staticmethod
    def get_thread_messages_serialized(thread_id: int) -> List[Dict]:
        msgs = MessageService.list_thread_messages(thread_id)
        return [serialize_message(m) for m in msgs]