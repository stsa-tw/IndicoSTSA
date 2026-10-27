"""List every form in the events API unless an organizer switched it off

0.6.0 added the switch with every row off, and a row exists for any form whose
STSA settings were saved for another reason, so an "off" that is already in the
table cannot be told from a choice.  Anything saved from here on is a choice.

Revision ID: e0f4a5b6c7d8
Revises: d9e3f4a5b6c7
Create Date: 2026-10-27 00:00:00.000000
"""

from alembic import op


revision = 'e0f4a5b6c7d8'
down_revision = 'd9e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('UPDATE plugin_stsa.regform_settings SET include_in_events_api = true')


def downgrade():
    # Back to what 0.6.0 left behind: off everywhere.
    op.execute('UPDATE plugin_stsa.regform_settings SET include_in_events_api = false')
