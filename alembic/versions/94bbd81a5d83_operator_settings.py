"""operator settings

Revision ID: 94bbd81a5d83
Revises: cad281bbc684
Create Date: 2026-11-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '94bbd81a5d83'
down_revision: Union[str, None] = 'cad281bbc684'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No seeded row (design D2 — defaults belong in code so they can change
    # without a data migration). ck_settings_singleton is the entire
    # "at most one row" guard: id is always 1.
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_prefs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('translation_merge_mode', sa.Text(), nullable=True),
        sa.Column('override_prefill', sa.Boolean(), nullable=True),
        sa.Column('default_target_langs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('id = 1', name='ck_settings_singleton'),
        sa.CheckConstraint(
            "translation_merge_mode IS NULL OR translation_merge_mode IN ('append', 'separate')",
            name='ck_settings_merge_mode',
        ),
    )


def downgrade() -> None:
    op.drop_table('settings')
