# api/utils/permissions.py

from functools import wraps

from flask import abort
from flask_login import current_user

from models import Profile


def get_current_profile() -> Profile | None:
    """
    Devuelve el Profile asociado al usuario logueado, o None si no existe.
    """
    if not current_user.is_authenticated:
        return None

    return Profile.query.filter_by(user_id=current_user.id).first()


def has_role(*role_names: str) -> bool:
    """
    Devuelve True si el usuario actual tiene alguno de los roles indicados
    por nombre (por ejemplo: "ADMIN", "PROFESOR", "ALUMNO").
    """
    profile = get_current_profile()
    if not profile:
        return False

    if not profile.role:
        return False

    return profile.role.name in role_names


def require_roles(*role_names: str):
    """
    Decorador para limitar una vista a ciertos roles.
    Uso:
        @require_roles("ADMIN")
        @require_roles("ADMIN", "PROFESOR")
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            profile = get_current_profile()
            if not profile or not profile.role or profile.role.name not in role_names:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def is_admin() -> bool:
    return has_role("ADMIN")


def is_teacher() -> bool:
    return has_role("PROFESOR")


def is_student() -> bool:
    return has_role("ALUMNO")