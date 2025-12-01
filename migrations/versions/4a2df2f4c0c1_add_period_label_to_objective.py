"""add period_label to objective

Revision ID: 4a2df2f4c0c1
Revises: 3c9ad3ccfbd1
Create Date: 2025-11-30 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a2df2f4c0c1'
down_revision = '3c9ad3ccfbd1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('objective', sa.Column('period_label', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('objective', 'period_label')
