"""Let a registration form say whether its registrations are listed by the events API

Revision ID: d9e3f4a5b6c7
Revises: c8d2e3f4a5b6
Create Date: 2026-10-26 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = 'd9e3f4a5b6c7'
down_revision = 'c8d2e3f4a5b6'
branch_labels = None
depends_on = None

SCHEMA = 'plugin_stsa'


def upgrade():
    op.add_column('regform_settings', sa.Column('include_in_events_api', sa.Boolean(), nullable=False,
                                                server_default='false'), schema=SCHEMA)
    op.alter_column('regform_settings', 'include_in_events_api', server_default=None, schema=SCHEMA)


def downgrade():
    op.drop_column('regform_settings', 'include_in_events_api', schema=SCHEMA)
