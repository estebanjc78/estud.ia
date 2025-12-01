from datetime import datetime

from extensions import db


class TaskHelpUsage(db.Model):
    """
    Registro temporal de ayudas utilizadas por un alumno antes de entregar la tarea.
    Se reinicia al completar la entrega para que cada intento tenga su propio conteo.
    """

    __tablename__ = "task_help_usage"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)

    count_baja = db.Column(db.Integer, nullable=False, default=0)
    count_media = db.Column(db.Integer, nullable=False, default=0)
    count_alta = db.Column(db.Integer, nullable=False, default=0)
    learning_style = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    institution = db.relationship("Institution")
    task = db.relationship("Task")
    student = db.relationship("Profile")

    __table_args__ = (
        db.UniqueConstraint("task_id", "student_profile_id", name="uq_task_help_usage"),
    )
