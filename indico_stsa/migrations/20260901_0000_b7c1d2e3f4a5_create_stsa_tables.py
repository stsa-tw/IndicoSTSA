"""Create the STSA tables

Revision ID: b7c1d2e3f4a5
Revises:
Create Date: 2026-09-01 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = 'b7c1d2e3f4a5'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'plugin_stsa'


def upgrade():
    op.execute(f'CREATE SCHEMA {SCHEMA}')

    op.create_table(
        'regform_settings',
        sa.Column('registration_form_id', sa.Integer(), nullable=False),
        sa.Column('member_discount_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('discount_type', sa.String(), nullable=False, server_default='percent'),
        sa.Column('discount_value', sa.Numeric(11, 2), nullable=False, server_default='0'),
        sa.Column('applies_to', sa.String(), nullable=False, server_default='base'),
        sa.Column('notice_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('group_login_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.CheckConstraint('discount_value >= 0', name='non_negative_discount'),
        sa.ForeignKeyConstraint(['registration_form_id'], ['event_registration.forms.id']),
        sa.PrimaryKeyConstraint('registration_form_id'),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table('regform_settings', schema=SCHEMA)
    op.execute(f'DROP SCHEMA {SCHEMA}')
