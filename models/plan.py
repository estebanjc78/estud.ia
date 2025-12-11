from __future__ import annotations

from datetime import datetime

from extensions import db


class Plan(db.Model):
    __tablename__ = "plan"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False, index=True)
    study_plan_id = db.Column(db.Integer, db.ForeignKey("study_plan.id"), nullable=True, unique=True)
    nombre = db.Column(db.String(255), nullable=False)
    anio_lectivo = db.Column(db.String(16), nullable=True)
    jurisdiccion = db.Column(db.String(120), nullable=True)
    descripcion_general = db.Column(db.Text, nullable=True)
    contenido_bruto = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    items = db.relationship(
        "PlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    study_plan = db.relationship("StudyPlan", back_populates="parsed_plan", uselist=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "study_plan_id": self.study_plan_id,
            "nombre": self.nombre,
            "anio_lectivo": self.anio_lectivo,
            "jurisdiccion": self.jurisdiccion,
            "descripcion_general": self.descripcion_general,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PlanDocument(db.Model):
    __tablename__ = "plan_document"

    id = db.Column(db.Integer, primary_key=True)
    study_plan_id = db.Column(db.Integer, db.ForeignKey("study_plan.id"), nullable=False, index=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False, index=True)
    curriculum_document_id = db.Column(db.Integer, db.ForeignKey("curriculum_document.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    subject_hint = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    study_plan = db.relationship("StudyPlan", back_populates="plan_documents")
    curriculum_document = db.relationship("CurriculumDocument")
    plan_items = db.relationship("PlanItem", back_populates="plan_document", cascade="all, delete-orphan")

    def label(self) -> str:
        base = self.title or "Documento"
        if self.subject_hint:
            return f"{base} · {self.subject_hint}"
        return base


class PlanItem(db.Model):
    __tablename__ = "plan_item"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False, index=True)
    plan_document_id = db.Column(db.Integer, db.ForeignKey("plan_document.id"), nullable=True, index=True)
    grado = db.Column(db.String(32), nullable=True)
    grado_normalizado = db.Column(db.String(32), nullable=True, index=True)
    area = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    metadata_json = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    plan = db.relationship("Plan", back_populates="items")
    plan_document = db.relationship("PlanDocument", back_populates="plan_items")

    @property
    def metadata_dict(self):
        return self.metadata_json or {}

    @metadata_dict.setter
    def metadata_dict(self, value):
        self.metadata_json = value

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "plan_document_id": self.plan_document_id,
            "grado": self.grado,
            "grado_normalizado": self.grado_normalizado,
            "area": self.area,
            "descripcion": self.descripcion,
            "metadata": self.metadata_dict,
        }
