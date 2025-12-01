"""add attachments and submissions tables

Revision ID: 6ce0a6c0c1a5
Revises: 16f6943e86a5
Create Date: 2025-11-30 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6ce0a6c0c1a5'
down_revision = '16f6943e86a5'
branch_labels = None
depends_on = None

evidence_type_enum = sa.Enum(
    'VISUAL',
    'ANALITICA',
    'AUDIO',
    name='evidencetypeenum',
)


def upgrade():
    evidence_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'attachment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('context_type', sa.String(length=50), nullable=False),
        sa.Column('context_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False, server_default='generic'),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('uploaded_by_profile_id', sa.Integer(), nullable=True),
        sa.Column('visibility', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by_profile_id'], ['profile.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_attachment_context',
        'attachment',
        ['context_type', 'context_id'],
        unique=False,
    )

    op.create_table(
        'task_submission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('student_profile_id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('help_level', sa.String(length=50), nullable=True),
        sa.Column('help_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_points', sa.Integer(), nullable=True),
        sa.Column('points_awarded', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['student_profile_id'], ['profile.id']),
        sa.ForeignKeyConstraint(['task_id'], ['task.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'submission_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('attachment_id', sa.Integer(), nullable=False),
        sa.Column('evidence_type', evidence_type_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachment.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['task_submission.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_submission_evidence_submission_type',
        'submission_evidence',
        ['submission_id', 'evidence_type'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_submission_evidence_submission_type', table_name='submission_evidence')
    op.drop_table('submission_evidence')
    op.drop_table('task_submission')
    op.drop_index('ix_attachment_context', table_name='attachment')
    op.drop_table('attachment')
    evidence_type_enum.drop(op.get_bind(), checkfirst=True)
