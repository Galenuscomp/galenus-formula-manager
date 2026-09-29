"""password links

Revision ID: c96a29efbfde
Revises: 7f0d43e43527
Create Date: 2026-09-29 20:39:23.748538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c96a29efbfde'
down_revision: Union[str, Sequence[str], None] = '7f0d43e43527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('password_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('token_digest', sa.String(length=64), nullable=False),
    sa.Column('purpose', sa.String(length=10), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_digest')
    )
    with op.batch_alter_table('password_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_tokens_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('password_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_password_tokens_user_id'))

    op.drop_table('password_tokens')
