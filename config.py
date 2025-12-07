# config.py
import os


class Config:
    SECRET_KEY = "super-secret-key"
    _BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    _DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "instance", "estudia.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{_DEFAULT_DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
