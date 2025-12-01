from __future__ import annotations

from typing import Iterable, Sequence

from models import Profile, RoleEnum


class ProfileService:
    """
    Utilidades centralizadas para obtener perfiles y validar roles/pertenencia.
    Evita duplicar queries en cada blueprint.
    """

    @staticmethod
    def get_profile_by_user(user_id: int) -> Profile | None:
        return Profile.query.filter_by(user_id=user_id).first()

    @staticmethod
    def require_profile(user_id: int) -> Profile:
        profile = ProfileService.get_profile_by_user(user_id)
        if not profile:
            raise ValueError("El usuario no tiene un perfil asociado.")
        return profile

    @staticmethod
    def ensure_institution_membership(profile: Profile, institution_id: int) -> None:
        if profile.institution_id != institution_id:
            raise PermissionError("El perfil no pertenece a la institución indicada.")

    @staticmethod
    def has_role(profile: Profile, *roles: str) -> bool:
        if not profile or not profile.role:
            return False
        return profile.role.name in roles

    @staticmethod
    def require_role(profile: Profile, *roles: str) -> None:
        if not ProfileService.has_role(profile, *roles):
            raise PermissionError("No tenés permisos para esta acción.")

    @staticmethod
    def normalize_participant_ids(profile_ids: Iterable[int]) -> list[int]:
        """
        Limpia la lista de IDs (quita None/duplicados) para threads/mensajes.
        """
        cleaned: list[int] = []
        for pid in profile_ids:
            if not pid:
                continue
            if pid not in cleaned:
                cleaned.append(pid)
        return cleaned
