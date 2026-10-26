"""add run_id to applications

Revision ID: a1b2c3d4e5f6
Revises: 150141dfc0ed
Create Date: 2026-06-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa # type: ignore

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '150141dfc0ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'applications',
        sa.Column('run_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_applications_run_id',
        'applications',
        'auto_apply_runs',
        ['run_id'],
        ['id']
    )
    op.create_index(
        'ix_applications_run_id',
        'applications',
        ['run_id']
    )


def downgrade() -> None:
    op.drop_index('ix_applications_run_id', table_name='applications')
    op.drop_constraint('fk_applications_run_id', 'applications', type_='foreignkey')
    op.drop_column('applications', 'run_id')