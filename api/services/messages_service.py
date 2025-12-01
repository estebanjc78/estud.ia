# api/services/messages_service.py

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from extensions import db
from models import Message, MessageThread, MessageThreadParticipant, Profile


class MessageService:
    """
    Servicio para manejar hilos de mensajes y mensajes.
    No depende de nada en api.*, solo de models y db → sin import circular.
    """

    @staticmethod
    def get_or_create_thread(
        context_type: str | None,
        context_id: int | None,
        participant_ids: List[int] | None = None,
        *,
        subject: str | None = None,
        force_new: bool = False,
        commit: bool = True,
    ) -> MessageThread:
        """
        Obtiene (o crea) un hilo de mensajes para un contexto dado
        (por ejemplo, una tarea, una lección, bitácora, etc.).

        - context_type: "task", "lesson", "bitacora", etc. (puede ser None para hilos manuales)
        - context_id: ID de la entidad (opcional si el hilo es manual).
        - participant_ids: lista de profile_id que deben estar en el hilo.
        - subject: título legible para el hilo.
        - force_new: si es True se crea un hilo nuevo ignorando coincidencias previas.
        """
        participant_ids = list(participant_ids or [])

        thread: MessageThread | None = None
        if not force_new:
            thread = MessageThread.query.filter_by(
                context_type=context_type,
                context_id=context_id,
            ).first()

        if not thread:
            thread = MessageThread(
                context_type=context_type,
                context_id=context_id,
                subject=subject,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_archived=False,
            )
            db.session.add(thread)
            db.session.flush()  # para tener thread.id
        else:
            if subject and thread.subject != subject:
                thread.subject = subject

        MessageService._ensure_participants(thread, participant_ids)
        thread.updated_at = datetime.utcnow()

        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return thread

    @staticmethod
    def send_message_to_context(
        context_type: str | None,
        context_id: int | None,
        sender_profile_id: int,
        text: str,
        participant_ids: List[int] | None = None,
        *,
        visibility: dict | None = None,
        thread_options: dict | None = None,
    ) -> Message:
        """
        Envía un mensaje dentro de un contexto lógico (tarea, lección, etc.).

        - context_type/context_id definen el hilo.
        - sender_profile_id: perfil que envía el mensaje.
        - participant_ids: otros perfiles que deben formar parte del hilo.
        - visibility: flags opcionales para mostrar/ocultar por rol.
        - thread_options: kwargs que se envían a get_or_create_thread (subject, force_new, etc.).
        """
        participant_ids = list(set(participant_ids or []))
        if sender_profile_id not in participant_ids:
            participant_ids.append(sender_profile_id)

        thread_options = dict(thread_options or {})
        thread = MessageService.get_or_create_thread(
            context_type=context_type,
            context_id=context_id,
            participant_ids=participant_ids,
            commit=False,
            **thread_options,
        )

        visibility = visibility or {}
        msg = Message(
            thread_id=thread.id,
            sender_profile_id=sender_profile_id,
            text=text,
            created_at=datetime.utcnow(),
            visible_for_student=visibility.get("student", True),
            visible_for_parent=visibility.get("parent", True),
            visible_for_teacher=visibility.get("teacher", True),
        )

        db.session.add(msg)
        thread.updated_at = datetime.utcnow()
        db.session.commit()
        return msg

    @staticmethod
    def list_thread_messages(
        thread_id: int, viewer_profile: Profile | None = None
    ) -> List[Message]:
        """
        Devuelve todos los mensajes de un thread, ordenados por fecha.
        """
        query = Message.query.filter_by(thread_id=thread_id)

        if viewer_profile and viewer_profile.role:
            role_name = viewer_profile.role.name
            if role_name == "ALUMNO":
                query = query.filter_by(visible_for_student=True)
            elif role_name == "PADRE":
                query = query.filter_by(visible_for_parent=True)
            else:
                # Profesor, admin o cualquier staff → por defecto visible_for_teacher
                query = query.filter_by(visible_for_teacher=True)

        return query.order_by(Message.created_at.asc()).all()

    @staticmethod
    def _ensure_participants(
        thread: MessageThread, participant_ids: Iterable[int]
    ) -> None:
        ids = [pid for pid in participant_ids if pid]
        if not ids:
            return

        existentes = {p.profile_id for p in thread.participants}
        for pid in ids:
            if pid not in existentes:
                db.session.add(
                    MessageThreadParticipant(
                        thread_id=thread.id,
                        profile_id=pid,
                        joined_at=datetime.utcnow(),
                    )
                )
        db.session.flush()
