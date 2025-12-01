# models/messages.py
from datetime import datetime

from sqlalchemy.orm import foreign

from extensions import db


class MessageThread(db.Model):
    """
    Hilo de conversación.
    Puede estar asociado a:
      - una tarea  (context_type='task',   context_id = task.id)
      - una lección(context_type='lesson', context_id = lesson.id)
      - un chat directo u otro contexto (context_type='direct', etc.)
    """
    __tablename__ = "message_thread"

    id = db.Column(db.Integer, primary_key=True)

    subject = db.Column(db.String(255), nullable=True)

    # contexto opcional
    context_type = db.Column(db.String(50), nullable=True)
    context_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_archived = db.Column(db.Boolean, default=False)

    # relaciones
    messages = db.relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    participants = db.relationship(
        "MessageThreadParticipant",
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MessageThreadParticipant(db.Model):
    """
    Participante de un hilo de mensajes.
    Permite N participantes por thread (profes, padres, alumnos, etc.).
    """
    __tablename__ = "message_thread_participant"

    id = db.Column(db.Integer, primary_key=True)

    thread_id = db.Column(
        db.Integer,
        db.ForeignKey("message_thread.id"),
        nullable=False,
    )
    profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False,
    )

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    # metadata útil a futuro
    last_read_at = db.Column(db.DateTime, nullable=True)

    thread = db.relationship("MessageThread", back_populates="participants")
    profile = db.relationship("Profile")  # sin back_populates por ahora


class Message(db.Model):
    """
    Mensaje individual dentro de un hilo.
    """
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)

    thread_id = db.Column(
        db.Integer,
        db.ForeignKey("message_thread.id"),
        nullable=False,
    )
    sender_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False,
    )

    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Flags de visibilidad según rol (por si mañana ocultamos algo a padres/alumnos)
    visible_for_student = db.Column(db.Boolean, default=True)
    visible_for_parent = db.Column(db.Boolean, default=True)
    visible_for_teacher = db.Column(db.Boolean, default=True)

    thread = db.relationship("MessageThread", back_populates="messages")
    sender = db.relationship("Profile")
    attachments = db.relationship(
        "Attachment",
        primaryjoin="and_(foreign(Attachment.context_id) == Message.id, Attachment.context_type == 'message')",
        viewonly=True,
        lazy="selectin",
    )
