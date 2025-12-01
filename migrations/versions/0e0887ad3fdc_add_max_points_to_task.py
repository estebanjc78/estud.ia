"""add max_points to task

Revision ID: 0e0887ad3fdc
Revises: 6ce0a6c0c1a5
Create Date: 2025-11-30 16:15:25.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e0887ad3fdc'
down_revision = '6ce0a6c0c1a5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('task', sa.Column('max_points', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('task', 'max_points')
