"""source accounts per user

Revision ID: b41d7e2c9a10
Revises: faca12b135c0
Create Date: 2026-09-30 07:40:00

Each user keeps their own source logins. Existing logins are given to the user
who saved them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b41d7e2c9a10'
down_revision: Union[str, Sequence[str], None] = 'faca12b135c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _new_table() -> None:
    op.create_table('source_accounts',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('username_encrypted', sa.Text(), nullable=False),
    sa.Column('password_encrypted', sa.Text(), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('check_ok', sa.Boolean(), nullable=True),
    sa.Column('check_message', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'source')
    )


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name == "sqlite":  # development databases: rebuild the table
        op.drop_table('source_accounts')
        _new_table()
        return
    op.add_column('source_accounts', sa.Column('user_id', sa.String(length=36), nullable=True))
    op.add_column('source_accounts', sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('source_accounts', sa.Column('check_ok', sa.Boolean(), nullable=True))
    op.add_column('source_accounts', sa.Column('check_message', sa.String(length=500), nullable=True))
    op.execute("UPDATE source_accounts SET user_id = updated_by")
    op.execute("DELETE FROM source_accounts WHERE user_id IS NULL")
    op.alter_column('source_accounts', 'user_id', nullable=False)
    op.drop_constraint('source_accounts_pkey', 'source_accounts', type_='primary')
    op.create_primary_key('source_accounts_pkey', 'source_accounts', ['user_id', 'source'])
    op.create_foreign_key('source_accounts_user_id_fkey', 'source_accounts', 'users', ['user_id'], ['id'],
                          ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema: one login per source again (keeps one of them)."""
    if op.get_bind().dialect.name == "sqlite":
        op.drop_table('source_accounts')
        op.create_table('source_accounts',
        sa.Column('source', sa.String(length=40), nullable=False),
        sa.Column('username_encrypted', sa.Text(), nullable=False),
        sa.Column('password_encrypted', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('source')
        )
        return
    op.execute("DELETE FROM source_accounts a USING source_accounts b "
               "WHERE a.source = b.source AND a.user_id > b.user_id")
    op.drop_constraint('source_accounts_user_id_fkey', 'source_accounts', type_='foreignkey')
    op.drop_constraint('source_accounts_pkey', 'source_accounts', type_='primary')
    op.create_primary_key('source_accounts_pkey', 'source_accounts', ['source'])
    op.drop_column('source_accounts', 'check_message')
    op.drop_column('source_accounts', 'check_ok')
    op.drop_column('source_accounts', 'checked_at')
    op.drop_column('source_accounts', 'user_id')
