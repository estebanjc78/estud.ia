from datetime import datetime

from extensions import db


class Attachment(db.Model):
    """
    Archivo adjunto asociado a cualquier entidad lógica
    (lesson, task, submission, message, bitacora, etc.).
    """

    __tablename__ = "attachment"

    id = db.Column(db.Integer, primary_key=True)

    # Contexto genérico de pertenencia
    context_type = db.Column(db.String(50), nullable=False)
    context_id = db.Column(db.Integer, nullable=False)

    # Tipo funcional del adjunto (ej: lesson_material, submission_visual, boletin, etc.)
    kind = db.Column(db.String(50), nullable=False, default="generic")

    # Metadata básica
    filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    # Quién lo subió y visibilidad
    uploaded_by_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=True,
    )
    visibility = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_by = db.relationship("Profile")

    __table_args__ = (
        db.Index("ix_attachment_context", "context_type", "context_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - helper
        return f"<Attachment {self.id} {self.context_type}:{self.context_id} {self.filename}>"
