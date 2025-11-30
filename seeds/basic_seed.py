# seeds/basic_seed.py
"""
Seed inicial para demos de la plataforma Estud.ia.
CREA:
- 1 institución demo
- 1 usuario admin + perfil
- 1 profesor + perfil
- 1 alumno + perfil
- 1 grado + sección
- 1 lesson demo
- 1 task demo

Este archivo NO debe ser importado por la aplicación.
Debe ejecutarse manualmente desde flask shell.
"""

from extensions import db
from models import (
    Institution,
    User,
    Profile,
    RoleEnum,
    Grade,
    Section,
    Lesson,
    Task,
)


def _get_or_create(model, defaults=None, **kwargs):
    """Función segura e idempotente. No duplica registros."""
    instance = model.query.filter_by(**kwargs).first()
    if instance:
        return instance, False

    params = {**kwargs}
    if defaults:
        params.update(defaults)

    instance = model(**params)
    db.session.add(instance)
    return instance, True


def run_basic_seed():
    print("🌱 Ejecutando SEED básico Estud.ia...")

    # -----------------------------
    # 1) INSTITUCIÓN
    # -----------------------------
    inst, created = _get_or_create(
        Institution,
        name="Colegio Estud.ia Demo",
        defaults={"logo_path": "/static/img/school_logo.png"},
    )
    if created:
        print("  ✔ Institución creada")
    else:
        print("  • Institución ya existía")

    # -----------------------------
    # 2) GRADO + SECCIÓN
    # -----------------------------
    grade, created = _get_or_create(
        Grade,
        institution_id=inst.id,
        name="5° Grado",
    )

    section, created = _get_or_create(
        Section,
        institution_id=inst.id,
        grade_id=grade.id,
        name="5°A",
    )

    # -----------------------------
    # 3) USUARIO ADMIN
    # -----------------------------
    admin_user, created = _get_or_create(
        User,
        email="admin@demo.com",
    )
    if created:
        admin_user.set_password("admin123")

    admin_profile, _ = _get_or_create(
        Profile,
        user_id=admin_user.id,
        institution_id=inst.id,
        role=RoleEnum.ADMIN,
        full_name="Administrador Demo",
    )

    # -----------------------------
    # 4) PROFESOR
    # -----------------------------
    prof_user, created = _get_or_create(
        User,
        email="profe@demo.com",
    )
    if created:
        prof_user.set_password("profe123")

    prof_profile, _ = _get_or_create(
        Profile,
        user_id=prof_user.id,
        institution_id=inst.id,
        role=RoleEnum.PROFESOR,
        full_name="Profe Demo",
    )

    # -----------------------------
    # 5) ALUMNO
    # -----------------------------
    alum_user, created = _get_or_create(
        User,
        email="alumno@demo.com",
    )
    if created:
        alum_user.set_password("alumno123")

    alum_profile, _ = _get_or_create(
        Profile,
        user_id=alum_user.id,
        institution_id=inst.id,
        role=RoleEnum.ALUMNO,
        full_name="Juan Pérez",
        section_id=section.id,
    )

    # -----------------------------
    # 6) LESSON DEMO
    # -----------------------------
    lesson, created = _get_or_create(
        Lesson,
        title="Fracciones",
        defaults={
            "description": "Introducción a fracciones para 5°A",
            "created_by": prof_profile.id,
        },
    )

    # -----------------------------
    # 7) TASK DEMO
    # -----------------------------
    task, created = _get_or_create(
        Task,
        lesson_id=lesson.id,
        title="Ejercicios de fracciones",
        defaults={
            "description": "Resolver ejercicios del cuaderno página 15",
        },
    )

    # -----------------------------
    # GUARDAR
    # -----------------------------
    db.session.commit()

    print("🌱 Seed ejecutado con éxito")
    print("   Usuarios creados:")
    print("     - admin@demo.com / admin123")
    print("     - profe@demo.com / profe123")
    print("     - alumno@demo.com / alumno123")
    print("   Lección demo: 'Fracciones'")
    print("   Tarea demo: 'Ejercicios de fracciones'")

    # -----------------------------
    # EJECUTAR 
    # -----------------------------
    #flask shell
    #>>> from seeds.basic_seed import run_basic_seed
    #>>> run_basic_seed()