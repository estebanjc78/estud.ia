"""add insight_report table

Revision ID: 7b1a2c4a8f1b
Revises: 4a2df2f4c0c1
Create Date: 2025-11-30 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b1a2c4a8f1b'
down_revision = '4a2df2f4c0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'insight_report',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('institution_id', sa.Integer(), sa.ForeignKey('institution.id'), nullable=False),
        sa.Column('author_profile_id', sa.Integer(), sa.ForeignKey('profile.id'), nullable=False),
        sa.Column('scope', sa.Enum('global', 'class', 'student', name='reportscope'), nullable=False, server_default='global'),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('target_label', sa.String(length=255), nullable=True),
        sa.Column('ai_model', sa.String(length=100), nullable=True),
        sa.Column('prompt_snapshot', sa.Text(), nullable=True),
        sa.Column('context_snapshot', sa.Text(), nullable=True),
        sa.Column('ai_draft', sa.Text(), nullable=True),
        sa.Column('final_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('insight_report')
    sa.Enum(name='reportscope').drop(op.get_bind(), checkfirst=True)
