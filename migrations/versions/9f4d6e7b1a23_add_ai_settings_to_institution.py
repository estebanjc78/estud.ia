"""add ai settings to institution

Revision ID: 9f4d6e7b1a23
Revises: 7b1a2c4a8f1b
Create Date: 2025-02-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f4d6e7b1a23'
down_revision = '7b1a2c4a8f1b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('institution', sa.Column('ai_provider', sa.String(length=50), nullable=True))
    op.add_column('institution', sa.Column('ai_model', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('institution', 'ai_model')
    op.drop_column('institution', 'ai_provider')
