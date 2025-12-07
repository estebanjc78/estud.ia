from datetime import datetime

from extensions import db


class CurriculumPrompt(db.Model):
    __tablename__ = "curriculum_prompt"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=True)
    context = db.Column(db.String(64), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    institution = db.relationship("Institution")


class CurriculumGradeAlias(db.Model):
    __tablename__ = "curriculum_grade_alias"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=True)
    alias = db.Column(db.String(80), nullable=False)
    normalized_value = db.Column(db.String(20), nullable=False)

    institution = db.relationship("Institution")


class CurriculumAreaKeyword(db.Model):
    __tablename__ = "curriculum_area_keyword"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=True)
    label = db.Column(db.String(120), nullable=False)
    pattern = db.Column(db.String(255), nullable=False)

    institution = db.relationship("Institution")
