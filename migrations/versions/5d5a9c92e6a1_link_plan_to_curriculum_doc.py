"""link study plan with curriculum document

Revision ID: 5d5a9c92e6a1
Revises: e317a92b17ab
Create Date: 2025-12-05 13:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d5a9c92e6a1'
down_revision = 'e317a92b17ab'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('study_plan', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('curriculum_document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_study_plan_curriculum_document',
            'curriculum_document',
            ['curriculum_document_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('study_plan', recreate='always') as batch_op:
        batch_op.drop_constraint('fk_study_plan_curriculum_document', type_='foreignkey')
        batch_op.drop_column('curriculum_document_id')
