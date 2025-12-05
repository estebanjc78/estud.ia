from datetime import datetime

from extensions import db


class PlatformTheme(db.Model):
    __tablename__ = "platform_theme"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, default="estud.ia Platform")
    subtitle = db.Column(db.String(255), nullable=True)
    logo_url = db.Column(db.String(512), nullable=True)

    primary_color = db.Column(db.String(7), nullable=True)
    secondary_color = db.Column(db.String(7), nullable=True)
    sidebar_color = db.Column(db.String(7), nullable=True)
    sidebar_text_color = db.Column(db.String(7), nullable=True)
    background_color = db.Column(db.String(7), nullable=True)
    login_background = db.Column(db.String(7), nullable=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    DEFAULTS = {
        "name": "estud.ia",
        "subtitle": "Potenciando la enseñanza",
        "logo_url": "/static/img/estudia_logo.png",
        "primary_color": "#0F766E",
        "secondary_color": "#0A4D4A",
        "sidebar_color": "#0B1A2A",
        "sidebar_text_color": "#d7e0ff",
        "background_color": "#f5efe6",
        "login_background": "#f5efe6",
    }

    @classmethod
    def current(cls):
        theme = cls.query.first()
        if not theme:
            theme = cls(**cls.DEFAULTS)
            db.session.add(theme)
            db.session.commit()
        return theme

    def as_config(self) -> dict:
        data = self.DEFAULTS.copy()
        data.update(
            {
                "school_name": self.name or data["name"],
                "school_logo": self.logo_url or data["logo_url"],
                "primary_color": self.primary_color or data["primary_color"],
                "secondary_color": self.secondary_color or data["secondary_color"],
                "sidebar_color": self.sidebar_color or data["sidebar_color"],
                "sidebar_text_color": self.sidebar_text_color or data["sidebar_text_color"],
                "background_color": self.background_color or data["background_color"],
                "login_background": self.login_background or data["login_background"],
            }
        )
        return data
