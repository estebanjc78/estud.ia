"""add rewards_config to institution

Revision ID: 1b66e5e2991b
Revises: 0e0887ad3fdc
Create Date: 2025-11-30 16:19:39.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b66e5e2991b'
down_revision = '0e0887ad3fdc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('institution', sa.Column('rewards_config', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('institution', 'rewards_config')
