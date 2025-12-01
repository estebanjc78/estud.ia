# seeds/basic_seed.py
"""
Seed integral para demos del MVP de estud.ia.

CREA (o reutiliza si ya existen):
    - Institución demo + configuración visual y recompensas
    - Grado, sección y plan de estudio con objetivos
    - Usuarios: admin, profesor, alumno, padre
    - Perfiles asociados con sus roles
    - Lesson + tareas asociadas con adjuntos
    - Mensajería de prueba, bitácora y submissions con evidencias

Modo de uso:
    flask shell
    >>> from seeds.basic_seed import run_basic_seed
    >>> run_basic_seed()
"""

from datetime import date, timedelta

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
    StudyPlan,
    Objective,
    MessageThread,
    Message,
    BitacoraEntrada,
    TaskSubmission,
    SubmissionEvidence,
    EvidenceTypeEnum,
    Attachment,
)

DEMO_PASSWORDS = {
    "admin@demo.com": "admin123",
    "profe@demo.com": "profe123",
    "alumno@demo.com": "alumno123",
    "padre@demo.com": "padre123",
}


def _get_or_create(model, defaults=None, **kwargs):
    instance = model.query.filter_by(**kwargs).first()
    if instance:
        return instance, False

    params = {**kwargs}
    if defaults:
        params.update(defaults)

    instance = model(**params)
    db.session.add(instance)
    return instance, True


def _ensure_user(email, full_name, role, institution_id, password=None, **extra_profile_fields):
    user, created = _get_or_create(User, email=email)
    if created or (not user.password_hash and password):
        user.set_password(password or DEMO_PASSWORDS.get(email, "changeme123"))

    profile, _ = _get_or_create(
        Profile,
        user_id=user.id,
        institution_id=institution_id,
        role=role,
        full_name=full_name,
        defaults=extra_profile_fields,
    )
    return user, profile


def _create_attachment(context_type, context_id, filename, kind, uploaded_by_profile_id):
    attachment = Attachment(
        context_type=context_type,
        context_id=context_id,
        kind=kind,
        filename=filename,
        storage_path=f"/demo/{filename}",
        mime_type="application/pdf",
        uploaded_by_profile_id=uploaded_by_profile_id,
    )
    db.session.add(attachment)
    db.session.flush()
    return attachment


def run_basic_seed():
    print("🌱 Ejecutando seed completo del MVP...")

    # 1. Institución y configuración visual
    inst, _ = _get_or_create(
        Institution,
        name="Colegio Estud.ia Demo",
        defaults={
            "short_code": "ESTUDIA",
            "logo_url": "/static/img/estudia_logo.png",
            "primary_color": "#2155CD",
            "secondary_color": "#A0B3FF",
            "rewards_config": [
                {"nombre": "Sticker dorado", "puntos": 50},
                {"nombre": "Tiempo extra recreo", "puntos": 120},
                {"nombre": "Líder de actividad", "puntos": 200},
            ],
        },
    )

    # 2. Grado + sección + plan
    grade, _ = _get_or_create(
        Grade,
        institution_id=inst.id,
        name="5° Grado",
    )
    section, _ = _get_or_create(
        Section,
        grade_id=grade.id,
        name="5°A",
    )
    plan, _ = _get_or_create(
        StudyPlan,
        institution_id=inst.id,
        grade_id=grade.id,
        name="Matemática 2025",
    )
    objective, _ = _get_or_create(
        Objective,
        study_plan_id=plan.id,
        title="Fracciones y equivalencias",
    )

    # 3. Usuarios y perfiles
    admin_user, admin_profile = _ensure_user(
        "admin@demo.com",
        "Admin Demo",
        RoleEnum.ADMIN,
        inst.id,
        password=DEMO_PASSWORDS["admin@demo.com"],
    )
    prof_user, prof_profile = _ensure_user(
        "profe@demo.com",
        "Profe Demo",
        RoleEnum.PROFESOR,
        inst.id,
        password=DEMO_PASSWORDS["profe@demo.com"],
    )
    student_user, student_profile = _ensure_user(
        "alumno@demo.com",
        "Juan Pérez",
        RoleEnum.ALUMNO,
        inst.id,
        password=DEMO_PASSWORDS["alumno@demo.com"],
        section_id=section.id,
    )
    parent_user, parent_profile = _ensure_user(
        "padre@demo.com",
        "María Pérez",
        RoleEnum.PADRE,
        inst.id,
        password=DEMO_PASSWORDS["padre@demo.com"],
    )

    # 4. Lesson + tasks
    lesson, _ = _get_or_create(
        Lesson,
        institution_id=inst.id,
        section_id=section.id,
        teacher_profile_id=prof_profile.id,
        objective_id=objective.id,
        title="Fracciones equivalentes",
        defaults={
            "description": "Sesión para reforzar equivalencias y representaciones.",
            "class_date": date.today(),
        },
    )

    task1, _ = _get_or_create(
        Task,
        lesson_id=lesson.id,
        institution_id=inst.id,
        title="Ejercicios de fracciones",
        defaults={
            "description": "Resolver ejercicios del cuaderno página 15",
            "due_date": date.today() + timedelta(days=2),
            "section_id": section.id,
            "objective_id": objective.id,
            "max_points": 100,
        },
    )

    task2, _ = _get_or_create(
        Task,
        lesson_id=lesson.id,
        institution_id=inst.id,
        title="Proyecto visual",
        defaults={
            "description": "Armar poster con fracciones equivalentes",
            "due_date": date.today() + timedelta(days=5),
            "section_id": section.id,
            "objective_id": objective.id,
            "max_points": 150,
        },
    )

    # Adjuntos para la primera tarea
    if not task1.attachments.count():
        _create_attachment("task", task1.id, "guia_fracciones.pdf", "task_material", prof_profile.id)

    # 5. Mensajes demo
    thread, _ = _get_or_create(
        MessageThread,
        context_type="lesson",
        context_id=lesson.id,
    )
    db.session.flush()
    if thread.messages.count() == 0:
        msg = Message(
            thread_id=thread.id,
            sender_profile_id=prof_profile.id,
            text="Familias, recuerden que el viernes tenemos presentación.",
        )
        db.session.add(msg)
        db.session.flush()
        _create_attachment("message", msg.id, "cronograma.pdf", "lesson_message", prof_profile.id)

    # 6. Bitácora demo
    if BitacoraEntrada.query.count() == 0:
        entry = BitacoraEntrada(
            institution_id=inst.id,
            student_profile_id=student_profile.id,
            author_profile_id=prof_profile.id,
            lesson_id=lesson.id,
            categoria="APRENDIZAJE",
            nota="Juan participó activamente y explicó un ejercicio a sus compañeros.",
            visible_para_padres=True,
            visible_para_alumno=True,
        )
        db.session.add(entry)
        db.session.flush()
        _create_attachment("bitacora", entry.id, "foto_poster.pdf", "bitacora_evidence", prof_profile.id)

    # 7. Submission demo
    submission, created = _get_or_create(
        TaskSubmission,
        task_id=task1.id,
        student_profile_id=student_profile.id,
        defaults={
            "comment": "Adjunto mi audio explicando el ejercicio 3.",
            "help_level": "BAJA",
            "help_count": 1,
            "max_points": 100,
            "points_awarded": 95,
        },
    )
    db.session.flush()
    if created or not submission.evidences:
        attachment = _create_attachment("submission", submission.id, "audio-explicacion.mp3", "submission_evidence", student_profile.id)
        db.session.add(
            SubmissionEvidence(
                submission_id=submission.id,
                attachment_id=attachment.id,
                evidence_type=EvidenceTypeEnum.AUDIO,
            )
        )

    db.session.commit()

    print("✅ Seed completo cargado.")
    print("   Usuarios:")
    for email, pwd in DEMO_PASSWORDS.items():
        print(f"     - {email} / {pwd}")
    print(f"   Lesson demo: {lesson.title}")
    print(f"   Tareas demo: {task1.title}, {task2.title}")
    print("   Mensaje, bitácora y submission creados con adjuntos para testear UI y APIs.")
