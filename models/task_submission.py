from datetime import datetime
import enum

from extensions import db


class EvidenceTypeEnum(str, enum.Enum):
    VISUAL = "VISUAL"
    ANALITICA = "ANALITICA"
    AUDIO = "AUDIO"


class TaskSubmission(db.Model):
    """
    Entrega de una tarea por parte de un alumno, con registros
    de ayudas utilizadas y puntos obtenidos.
    """

    __tablename__ = "task_submission"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.Column(db.Text, nullable=True)

    # Información de ayudas / puntos
    help_level = db.Column(db.String(50), nullable=True)
    help_count = db.Column(db.Integer, default=0)
    help_breakdown = db.Column(db.JSON, nullable=True)
    max_points = db.Column(db.Integer, nullable=True)
    points_awarded = db.Column(db.Integer, nullable=True)

    task = db.relationship("Task", back_populates="submissions")
    student = db.relationship("Profile", backref="task_submissions")

    evidences = db.relationship(
        "SubmissionEvidence",
        back_populates="submission",
        cascade="all, delete-orphan",
    )


class SubmissionEvidence(db.Model):
    """
    Evidencia asociada a una entrega (visual, analítica, audio, etc.).
    Cada evidencia referencia un Attachment reutilizable.
    """

    __tablename__ = "submission_evidence"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("task_submission.id"),
        nullable=False,
    )
    attachment_id = db.Column(
        db.Integer,
        db.ForeignKey("attachment.id"),
        nullable=False,
    )
    evidence_type = db.Column(
        db.Enum(EvidenceTypeEnum),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship("TaskSubmission", back_populates="evidences")
    attachment = db.relationship("Attachment")

    __table_args__ = (
        db.Index(
            "ix_submission_evidence_submission_type",
            "submission_id",
            "evidence_type",
        ),
    )
