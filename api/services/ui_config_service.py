# api/services/ui_config_service.py

from __future__ import annotations

from models import Profile, Institution, RoleEnum, PlatformTheme


class UIConfigService:
    @staticmethod
    def get_ui_config_for_user(user) -> dict:
        """
        Devuelve la configuración visual basada en la institución del usuario.
        Estructura básica:
        {
            "school_name": str | None,
            "school_logo": str | None,
            "primary_color": str | None,
            "secondary_color": str | None,
            "recompensas": list[dict]
        }
        """
        base_config = {
            "school_name": None,
            "school_logo": None,
            "primary_color": None,
            "secondary_color": None,
            "sidebar_color": None,
            "sidebar_text_color": None,
            "background_color": None,
            "login_background": None,
            "recompensas": [],
        }

        if not user or not getattr(user, "id", None):
            theme = PlatformTheme.current()
            cfg = theme.as_config()
            cfg["recompensas"] = []
            return cfg

        profile = Profile.query.filter_by(user_id=user.id).first()
        owner_role = getattr(RoleEnum, "ADMIN", None)
        if profile and profile.role == owner_role:
            cfg = PlatformTheme.current().as_config()
            cfg["recompensas"] = []
            return cfg
        if not profile or not profile.institution:
            theme = PlatformTheme.current()
            cfg = theme.as_config()
            cfg["recompensas"] = []
            return cfg

        inst = profile.institution

        rewards = inst.rewards_config or []

        base_config.update(
            {
                "school_name": inst.name,
                "school_logo": inst.logo_url,
                "primary_color": inst.primary_color,
                "secondary_color": inst.secondary_color,
                "sidebar_color": inst.primary_color,
                "sidebar_text_color": None,
                "background_color": None,
                "login_background": None,
                "recompensas": rewards,
            }
        )

        return base_config

    @staticmethod
    def _default_rewards() -> list[dict]:
        """
        Placeholder hasta tener CMS real de recompensas.
        """
        return []
