"""examples prefill count and max providers

Revision ID: c3f8a0d2e5b1
Revises: b7e2a4f1c6d8
Create Date: 2026-11-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3f8a0d2e5b1'
down_revision: Union[str, None] = 'b7e2a4f1c6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('examples_count', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('examples_max_providers', sa.Integer(), nullable=True))
    op.create_check_constraint(
        'ck_settings_examples_count',
        'settings',
        'examples_count IS NULL OR examples_count BETWEEN 1 AND 10',
    )
    op.create_check_constraint(
        'ck_settings_examples_max_providers',
        'settings',
        'examples_max_providers IS NULL OR examples_max_providers BETWEEN 1 AND 10',
    )


def downgrade() -> None:
    op.drop_constraint('ck_settings_examples_max_providers', 'settings', type_='check')
    op.drop_constraint('ck_settings_examples_count', 'settings', type_='check')
    op.drop_column('settings', 'examples_max_providers')
    op.drop_column('settings', 'examples_count')
