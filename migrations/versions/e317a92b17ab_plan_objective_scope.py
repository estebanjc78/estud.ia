"""allow plan without grade and enrich objectives

Revision ID: e317a92b17ab
Revises: df4f6b8f9a9a
Create Date: 2025-12-05 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e317a92b17ab'
down_revision = 'df4f6b8f9a9a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('study_plan', recreate='always') as batch_op:
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column('jurisdiction', sa.String(length=120), nullable=True))

    with op.batch_alter_table('objective', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('grade_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('subject_label', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('class_ideas', sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            'fk_objective_grade_id_grade',
            'grade',
            ['grade_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('objective', recreate='always') as batch_op:
        batch_op.drop_constraint('fk_objective_grade_id_grade', type_='foreignkey')
        batch_op.drop_column('class_ideas')
        batch_op.drop_column('subject_label')
        batch_op.drop_column('grade_id')

    with op.batch_alter_table('study_plan', recreate='always') as batch_op:
        batch_op.drop_column('jurisdiction')
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.Integer(),
            nullable=False,
        )
