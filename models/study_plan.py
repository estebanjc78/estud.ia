from extensions import db

class StudyPlan(db.Model):
    __tablename__ = "study_plan"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grade.id"), nullable=True)
    curriculum_document_id = db.Column(db.Integer, db.ForeignKey("curriculum_document.id"), nullable=True)

    name = db.Column(db.String(255), nullable=False)            # Ej: "Matemática 3° primaria 2025"
    year = db.Column(db.Integer, nullable=True)                 # Opcional: año lectivo
    description = db.Column(db.Text, nullable=True)
    jurisdiction = db.Column(db.String(120), nullable=True)

    is_active = db.Column(db.Boolean, default=True)

    # Relación con objetivos
    objectives = db.relationship("Objective", back_populates="study_plan", cascade="all, delete-orphan")
    grade = db.relationship("Grade")
    curriculum_document = db.relationship("CurriculumDocument")


class Objective(db.Model):
    __tablename__ = "objective"

    id = db.Column(db.Integer, primary_key=True)
    study_plan_id = db.Column(db.Integer, db.ForeignKey("study_plan.id"), nullable=False)

    # 🔹 NUEVA COLUMNA PARA RECURSIVIDAD
    parent_objective_id = db.Column(db.Integer, db.ForeignKey("objective.id"), nullable=True)

    grade_id = db.Column(db.Integer, db.ForeignKey("grade.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    subject_label = db.Column(db.String(120), nullable=True)
    class_ideas = db.Column(db.Text, nullable=True)
    order_index = db.Column(db.Integer, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    period_label = db.Column(db.String(100), nullable=True)

    study_plan = db.relationship("StudyPlan", back_populates="objectives")
    grade = db.relationship("Grade")

    # 🔹 NUEVA RELACIÓN RECURSIVA (PARENT → CHILDREN)
    parent = db.relationship("Objective", remote_side=[id], backref="children")
