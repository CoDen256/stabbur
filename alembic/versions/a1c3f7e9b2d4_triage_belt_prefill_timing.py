"""note-triage prefill timing

Revision ID: a1c3f7e9b2d4
Revises: 94bbd81a5d83
Create Date: 2026-11-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c3f7e9b2d4'
down_revision: Union[str, None] = '94bbd81a5d83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('prefill_timing', sa.Text(), nullable=True))
    op.create_check_constraint(
        'ck_settings_prefill_timing',
        'settings',
        "prefill_timing IS NULL OR prefill_timing IN ('on_open', 'on_demand')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_settings_prefill_timing', 'settings', type_='check')
    op.drop_column('settings', 'prefill_timing')
