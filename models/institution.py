from datetime import datetime
from extensions import db

class Institution(db.Model):
    __tablename__ = "institution"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    short_code = db.Column(db.String(50), nullable=True, unique=True)
    logo_url = db.Column(db.String(512), nullable=True)
    primary_color = db.Column(db.String(7), nullable=True)
    secondary_color = db.Column(db.String(7), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    grades = db.relationship("Grade", back_populates="institution", cascade="all, delete-orphan")
    profiles = db.relationship("Profile", back_populates="institution", cascade="all, delete-orphan")


class Grade(db.Model):
    __tablename__ = "grade"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(50), nullable=True)
    order_index = db.Column(db.Integer, nullable=True)

    institution = db.relationship("Institution", back_populates="grades")
    sections = db.relationship("Section", back_populates="grade", cascade="all, delete-orphan")


class Section(db.Model):
    __tablename__ = "section"

    id = db.Column(db.Integer, primary_key=True)
    grade_id = db.Column(db.Integer, db.ForeignKey("grade.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)

    grade = db.relationship("Grade", back_populates="sections")
    students = db.relationship("Profile", back_populates="section")