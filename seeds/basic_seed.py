from extensions import db
from models import Institution, Grade, Section, User, Profile, RoleEnum

def seed_basic_data():
    inst = Institution(
        name="Colegio Demo Estud.ia",
        short_code="DEMO",
        logo_url="https://example.com/logo.png",
        primary_color="#005f73",
        secondary_color="#ffb703",
    )
    db.session.add(inst)
    db.session.flush()

    grade3 = Grade(
        institution_id=inst.id,
        name="3° Primaria",
        level="Primaria",
        order_index=3,
    )
    db.session.add(grade3)
    db.session.flush()

    section_a = Section(
        grade_id=grade3.id,
        name="A",
    )
    db.session.add(section_a)
    db.session.flush()

    admin_user = User(email="admin@demo.edu")
    admin_user.set_password("admin123")

    teacher_user = User(email="profe@demo.edu")
    teacher_user.set_password("profesor123")

    student_user = User(email="alumno@demo.edu")
    student_user.set_password("alumno123")

    db.session.add_all([admin_user, teacher_user, student_user])
    db.session.flush()

    admin_profile = Profile(
        user_id=admin_user.id,
        institution_id=inst.id,
        role=RoleEnum.ADMIN_COLEGIO,
        full_name="Admin Colegio Demo",
    )

    teacher_profile = Profile(
        user_id=teacher_user.id,
        institution_id=inst.id,
        role=RoleEnum.PROFESOR,
        full_name="María Gómez",
    )

    student_profile = Profile(
        user_id=student_user.id,
        institution_id=inst.id,
        role=RoleEnum.ALUMNO,
        full_name="Juan Pérez",
        section_id=section_a.id,
    )

    db.session.add_all([admin_profile, teacher_profile, student_profile])
    db.session.commit()