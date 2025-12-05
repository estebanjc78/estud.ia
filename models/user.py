from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from .roles import RoleEnum
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profiles = db.relationship("Profile", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Profile(db.Model):
    __tablename__ = "profile"

    activation_token = db.Column(db.String(255), nullable=True)
    activation_expires = db.Column(db.DateTime, nullable=True)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=True)
    role = db.Column(db.Enum(RoleEnum), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)

    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)

    user = db.relationship("User", back_populates="profiles")
    institution = db.relationship("Institution", back_populates="profiles")
    section = db.relationship("Section", back_populates="students") 
