from datetime import datetime
from extensions import db


class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)

    # A qué institución pertenece esta tarea
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)

    # A qué clase (Lesson) está ligada
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=True)

    # Opcional: también podemos ligar directamente al objetivo
    objective_id = db.Column(db.Integer, db.ForeignKey("objective.id"), nullable=True)

    # Sección / grupo al que va dirigida (2°A, 3°B, etc.)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)

    # Título y descripción de la tarea
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Fecha de entrega
    due_date = db.Column(db.Date, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones sencillas (nos sirven luego para bitácora e insights)
    institution = db.relationship("Institution", backref="tasks")
    lesson = db.relationship("Lesson", backref="tasks")
    objective = db.relationship("Objective", backref="tasks")
    section = db.relationship("Section", backref="tasks")