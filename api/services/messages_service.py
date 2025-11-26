# api/services/messages_service.py

from datetime import datetime
from typing import List

from extensions import db
from models import Message, MessageThread, MessageThreadParticipant


class MessageService:
    """
    Servicio para manejar hilos de mensajes y mensajes.
    No depende de nada en api.*, solo de models y db → sin import circular.
    """

    @staticmethod
    def get_or_create_thread(
        context_type: str,
        context_id: int,
        participant_ids: List[int],
    ) -> MessageThread:
        """
        Obtiene (o crea) un hilo de mensajes para un contexto dado
        (por ejemplo, una tarea, una lección, bitácora, etc.).

        - context_type: "task", "lesson", "bitacora", etc.
        - context_id: ID de la entidad.
        - participant_ids: lista de profile_id que deben estar en el hilo.
        """
        thread = MessageThread.query.filter_by(
            context_type=context_type,
            context_id=context_id,
        ).first()

        if not thread:
            thread = MessageThread(
                context_type=context_type,
                context_id=context_id,
                created_at=datetime.utcnow(),
            )
            db.session.add(thread)
            db.session.flush()  # para tener thread.id

        # Asegurar participantes
        existentes = {p.profile_id for p in thread.participants}
        for pid in participant_ids:
            if pid not in existentes:
                db.session.add(
                    MessageThreadParticipant(
                        thread_id=thread.id,
                        profile_id=pid,
                    )
                )

        db.session.commit()
        return thread

    @staticmethod
    def send_message_to_context(
        context_type: str,
        context_id: int,
        sender_profile_id: int,
        text: str,
        participant_ids: List[int] | None = None,
    ) -> Message:
        """
        Envía un mensaje dentro de un contexto lógico (tarea, lección, etc.).

        - context_type/context_id definen el hilo.
        - sender_profile_id: perfil que envía el mensaje.
        - participant_ids: otros perfiles que deben formar parte del hilo.
        """
        participant_ids = list(set(participant_ids or []))
        if sender_profile_id not in participant_ids:
            participant_ids.append(sender_profile_id)

        thread = MessageService.get_or_create_thread(
            context_type=context_type,
            context_id=context_id,
            participant_ids=participant_ids,
        )

        msg = Message(
            thread_id=thread.id,
            sender_profile_id=sender_profile_id,
            text=text,
            created_at=datetime.utcnow(),
        )

        db.session.add(msg)
        db.session.commit()
        return msg

    @staticmethod
    def list_thread_messages(thread_id: int) -> List[Message]:
        """
        Devuelve todos los mensajes de un thread, ordenados por fecha.
        """
        return (
            Message.query.filter_by(thread_id=thread_id)
            .order_by(Message.created_at.asc())
            .all()
        )