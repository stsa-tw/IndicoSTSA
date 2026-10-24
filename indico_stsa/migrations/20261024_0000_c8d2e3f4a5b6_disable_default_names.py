"""Let First name and Last name be switched off

Revision ID: c8d2e3f4a5b6
Revises: b7c1d2e3f4a5
Create Date: 2026-10-24 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = 'c8d2e3f4a5b6'
down_revision = 'b7c1d2e3f4a5'
branch_labels = None
depends_on = None

SCHEMA = 'plugin_stsa'


def upgrade():
    op.add_column('regform_settings', sa.Column('first_name_disabled', sa.Boolean(), nullable=False,
                                                server_default='false'), schema=SCHEMA)
    op.add_column('regform_settings', sa.Column('last_name_disabled', sa.Boolean(), nullable=False,
                                                server_default='false'), schema=SCHEMA)
    op.alter_column('regform_settings', 'first_name_disabled', server_default=None, schema=SCHEMA)
    op.alter_column('regform_settings', 'last_name_disabled', server_default=None, schema=SCHEMA)


def downgrade():
    op.drop_column('regform_settings', 'last_name_disabled', schema=SCHEMA)
    op.drop_column('regform_settings', 'first_name_disabled', schema=SCHEMA)
