"""add curriculum prompts and keyword catalogs

Revision ID: 7e79bfe8c7c3
Revises: 5d5a9c92e6a1
Create Date: 2025-12-05 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '7e79bfe8c7c3'
down_revision = '5d5a9c92e6a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'curriculum_prompt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_id', sa.Integer(), nullable=True),
        sa.Column('context', sa.String(length=64), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['institution_id'], ['institution.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('institution_id', 'context', name='uq_curriculum_prompt_context')
    )

    op.create_table(
        'curriculum_grade_alias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_id', sa.Integer(), nullable=True),
        sa.Column('alias', sa.String(length=80), nullable=False),
        sa.Column('normalized_value', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['institution_id'], ['institution.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'curriculum_area_keyword',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_id', sa.Integer(), nullable=True),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('pattern', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['institution_id'], ['institution.id']),
        sa.PrimaryKeyConstraint('id')
    )

    grade_alias_table = sa.table(
        'curriculum_grade_alias',
        sa.column('institution_id', sa.Integer),
        sa.column('alias', sa.String),
        sa.column('normalized_value', sa.String),
    )
    default_grade_aliases = [
        ("primero", "1"),
        ("primer", "1"),
        ("1", "1"),
        ("segundo", "2"),
        ("2", "2"),
        ("tercero", "3"),
        ("3", "3"),
        ("cuarto", "4"),
        ("4", "4"),
        ("quinto", "5"),
        ("5", "5"),
        ("sexto", "6"),
        ("6", "6"),
        ("séptimo", "7"),
        ("septimo", "7"),
        ("7", "7"),
    ]
    op.bulk_insert(
        grade_alias_table,
        [{"institution_id": None, "alias": alias, "normalized_value": value} for alias, value in default_grade_aliases],
    )

    area_keyword_table = sa.table(
        'curriculum_area_keyword',
        sa.column('institution_id', sa.Integer),
        sa.column('label', sa.String),
        sa.column('pattern', sa.String),
    )
    default_area_keywords = [
        ("Prácticas del Lenguaje", r"pr[aá]cticas?\s+del\s+lenguaje"),
        ("Matemática", r"matem[aá]tica"),
        ("Ciencias Naturales", r"ciencias?\s+naturales?"),
        ("Ciencias Sociales", r"ciencias?\s+sociales?"),
        ("Educación Física", r"educaci[oó]n\s+f[ií]sica"),
        ("Educación Tecnológica", r"educaci[oó]n\s+tecnol[oó]gica"),
        ("Formación Ética y Ciudadana", r"formaci[oó]n\s+[eé]tica\s+y\s+ciudadana"),
        ("Informática", r"inform[aá]tica"),
        ("Artes", r"artes?"),
        ("Música", r"m[uú]sica"),
        ("Plástica", r"pl[aá]stica"),
        ("Teatro", r"teatro"),
    ]
    op.bulk_insert(
        area_keyword_table,
        [{"institution_id": None, "label": label, "pattern": pattern} for label, pattern in default_area_keywords],
    )

    prompt_table = sa.table(
        'curriculum_prompt',
        sa.column('institution_id', sa.Integer),
        sa.column('context', sa.String),
        sa.column('prompt_text', sa.Text),
        sa.column('is_active', sa.Boolean),
        sa.column('updated_at', sa.DateTime),
    )
    default_prompt = (
        "Analiza el documento curricular sin asumir ningún formato fijo y detecta automáticamente grados/cursos, "
        "materias/áreas y objetivos de aprendizaje (también llamados competencias, propósitos o resultados esperados). "
        "Los términos pueden variar (ej. “4°”, “cuarto grado”, “grade 4”; “Lengua”, “Language Arts”, etc.). "
        "Organiza la información deduciendo el contexto de títulos, subtítulos y secciones, sin inventar datos. "
        "Devuelve un único JSON claro con la jerarquía grado→materia→objetivos."
    )
    op.bulk_insert(
        prompt_table,
        [{
            "institution_id": None,
            "context": "curriculum_parser",
            "prompt_text": default_prompt,
            "is_active": True,
            "updated_at": datetime.utcnow(),
        }],
    )


def downgrade():
    op.drop_table('curriculum_area_keyword')
    op.drop_table('curriculum_grade_alias')
    op.drop_table('curriculum_prompt')
