from datetime import datetime
from enum import Enum

from sqlalchemy.orm import foreign

from extensions import db


class BitacoraCategoria(Enum):
    DISCIPLINA = "disciplina"
    APRENDIZAJE = "aprendizaje"
    EMOCIONAL = "emocional"
    OTRO = "otro"


class BitacoraEntrada(db.Model):
    """
    Bitácora manual de eventos relevantes sobre un alumno.
    NO es un log técnico del sistema.
    """
    __tablename__ = "bitacora_entrada"

    id = db.Column(db.Integer, primary_key=True)

    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institution.id"),
        nullable=False,
    )

    student_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False,
    )

    author_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False,
    )

    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lesson.id"),
        nullable=True,
    )

    categoria = db.Column(
        db.Enum(BitacoraCategoria),
        nullable=False,
        default=BitacoraCategoria.APRENDIZAJE,
    )

    nota = db.Column(db.Text, nullable=False)

    visible_para_padres = db.Column(db.Boolean, default=True)
    visible_para_alumno = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    student_profile = db.relationship(
        "Profile",
        foreign_keys=[student_profile_id],
        backref="bitacora_entradas",
    )

    author_profile = db.relationship(
        "Profile",
        foreign_keys=[author_profile_id],
        backref="bitacora_autor_entradas",
    )

    lesson = db.relationship("Lesson", backref="bitacora_entradas")
    institution = db.relationship("Institution", backref="bitacora_entradas")
    attachments = db.relationship(
        "Attachment",
        primaryjoin="and_(foreign(Attachment.context_id) == BitacoraEntrada.id, "
                    "Attachment.context_type == 'bitacora')",
        viewonly=True,
        lazy="selectin",
    )
