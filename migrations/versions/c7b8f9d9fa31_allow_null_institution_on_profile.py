"""allow null institution on profile

Revision ID: c7b8f9d9fa31
Revises: ab23f0b7a54d
Create Date: 2025-12-04 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7b8f9d9fa31'
down_revision = 'ab23f0b7a54d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.alter_column('institution_id', existing_type=sa.Integer(), nullable=True)

    op.execute("UPDATE profile SET institution_id = NULL WHERE role = 'ADMIN'")


def downgrade():
    op.execute("UPDATE profile SET institution_id = (SELECT institution.id FROM institution ORDER BY institution.id LIMIT 1) WHERE institution_id IS NULL")
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.alter_column('institution_id', existing_type=sa.Integer(), nullable=False)
