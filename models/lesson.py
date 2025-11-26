from datetime import datetime, time
from extensions import db


class Lesson(db.Model):
    __tablename__ = "lesson"

    id = db.Column(db.Integer, primary_key=True)

    # A qué institución pertenece esta clase
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)

    # Sección / grupo (2°A, 3°B, etc.)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)

    # Profesor que dicta la clase (Profile con rol PROFESOR)
    teacher_profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=True)

    # Objetivo del plan de estudio al que está ligada esta clase
    objective_id = db.Column(db.Integer, db.ForeignKey("objective.id"), nullable=True)

    # Datos básicos de la clase
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Cuándo se dicta
    class_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones (no imprescindibles para el MVP pero útiles)
    institution = db.relationship("Institution", backref="lessons")
    section = db.relationship("Section", backref="lessons")
    teacher_profile = db.relationship("Profile", backref="lessons")
    objective = db.relationship("Objective", backref="lessons")