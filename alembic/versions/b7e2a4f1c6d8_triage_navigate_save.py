"""triage navigate save preference

Revision ID: b7e2a4f1c6d8
Revises: 8589dc3d360d
Create Date: 2026-11-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7e2a4f1c6d8'
down_revision: Union[str, None] = '8589dc3d360d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('triage_navigate_save', sa.Text(), nullable=True))
    op.create_check_constraint(
        'ck_settings_triage_navigate_save',
        'settings',
        "triage_navigate_save IS NULL OR triage_navigate_save IN ('autosave', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_settings_triage_navigate_save', 'settings', type_='check')
    op.drop_column('settings', 'triage_navigate_save')
