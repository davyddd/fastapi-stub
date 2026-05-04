"""add user table

Revision ID: 6a7c2f2d3b11
Revises:
Create Date: 2026-05-04 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6a7c2f2d3b11'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk__user'),
        sa.UniqueConstraint('email', name='uq__user__email'),
    )
    op.create_index('ix__user__email', 'user', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index('ix__user__email', table_name='user')
    op.drop_table('user')
