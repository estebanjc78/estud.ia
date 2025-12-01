# api/services/ui_config_service.py

from __future__ import annotations

from models import Profile, Institution


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
            "recompensas": UIConfigService._default_rewards(),
        }

        if not user or not getattr(user, "id", None):
            inst = Institution.query.first()
            if inst:
                base_config.update(
                    {
                        "school_name": inst.name,
                        "school_logo": inst.logo_url,
                        "primary_color": inst.primary_color,
                        "secondary_color": inst.secondary_color,
                        "recompensas": inst.rewards_config or UIConfigService._default_rewards(),
                    }
                )
            return base_config

        profile = Profile.query.filter_by(user_id=user.id).first()
        if not profile or not profile.institution:
            inst = Institution.query.first()
            if inst:
                base_config.update(
                    {
                        "school_name": inst.name,
                        "school_logo": inst.logo_url,
                        "primary_color": inst.primary_color,
                        "secondary_color": inst.secondary_color,
                        "recompensas": inst.rewards_config or UIConfigService._default_rewards(),
                    }
                )
            return base_config

        inst = profile.institution

        rewards = inst.rewards_config or UIConfigService._default_rewards()

        base_config.update(
            {
                "school_name": inst.name,
                "school_logo": inst.logo_url,
                "primary_color": inst.primary_color,
                "secondary_color": inst.secondary_color,
                "recompensas": rewards,
            }
        )

        return base_config

    @staticmethod
    def _default_rewards() -> list[dict]:
        """
        Placeholder hasta tener CMS real de recompensas.
        """
        return [
            {"nombre": "Sticker dorado", "puntos": 50},
            {"nombre": "Tiempo extra recreo", "puntos": 120},
            {"nombre": "Líder de actividad", "puntos": 200},
        ]
