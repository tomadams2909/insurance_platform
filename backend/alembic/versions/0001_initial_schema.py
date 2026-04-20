"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('primary_colour', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('finance_company', sa.String(), nullable=True),
        sa.Column('allowed_products', sa.JSON(), nullable=True),
        sa.Column('favicon_url', sa.String(), nullable=True),
        sa.Column('broker_commission_rate', sa.Numeric(5, 2), nullable=False, server_default='15.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_tenants_id', 'tenants', ['id'])
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])

    op.create_table(
        'dealers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('address', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dealers_id', 'dealers', ['id'])

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.Enum(
            'SUPER_ADMIN', 'TENANT_ADMIN', 'UNDERWRITER', 'BROKER', 'INSURED', name='userrole'
        ), nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('dealer_id', sa.Integer(), sa.ForeignKey('dealers.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'dealer_commissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dealer_id', sa.Integer(), sa.ForeignKey('dealers.id'), nullable=False),
        sa.Column('product', sa.Enum(
            'GAP', 'VRI', 'COSMETIC', 'TYRE_ESSENTIAL', 'TYRE_PLUS', 'TLP', name='producttype'
        ), nullable=True),
        sa.Column('commission_type', sa.Enum('PERCENTAGE', 'FLAT_FEE', name='commissiontype'), nullable=False),
        sa.Column('commission_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_dealer_commissions_id', 'dealer_commissions', ['id'])

    op.create_table(
        'quotes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('product', sa.Enum(
            'GAP', 'VRI', 'COSMETIC', 'TYRE_ESSENTIAL', 'TYRE_PLUS', 'TLP',
            name='producttype', create_type=False,
        ), nullable=False),
        sa.Column('status', sa.Enum(
            'QUICK_QUOTE', 'QUOTED', 'DECLINED', 'NOT_TAKEN_UP', 'BOUND', name='quotestatus'
        ), nullable=False, server_default='QUICK_QUOTE'),
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('customer_dob', sa.String(), nullable=True),
        sa.Column('customer_email', sa.String(), nullable=True),
        sa.Column('customer_address', sa.JSON(), nullable=True),
        sa.Column('term_months', sa.Integer(), nullable=True),
        sa.Column('vehicle_category', sa.Integer(), nullable=True),
        sa.Column('product_fields', sa.JSON(), nullable=True),
        sa.Column('calculated_premium', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('payment_type', sa.Enum('CASH', 'FINANCE', name='paymenttype'), nullable=False, server_default='CASH'),
        sa.Column('finance_deposit', sa.Numeric(10, 2), nullable=True),
        sa.Column('finance_term_months', sa.Integer(), nullable=True),
        sa.Column('finance_breakdown', sa.JSON(), nullable=True),
        sa.Column('dealer_id', sa.Integer(), sa.ForeignKey('dealers.id'), nullable=True),
    )
    op.create_index('ix_quotes_id', 'quotes', ['id'])

    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quotes.id'), nullable=False),
        sa.Column('registration', sa.String(), nullable=True),
        sa.Column('make', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('purchase_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('purchase_date', sa.String(), nullable=True),
        sa.Column('finance_type', sa.String(), nullable=True),
        sa.UniqueConstraint('quote_id'),
    )
    op.create_index('ix_vehicles_id', 'vehicles', ['id'])

    op.create_table(
        'policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('quotes.id'), nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('dealer_id', sa.Integer(), sa.ForeignKey('dealers.id'), nullable=True),
        sa.Column('product', sa.Enum(
            'GAP', 'VRI', 'COSMETIC', 'TYRE_ESSENTIAL', 'TYRE_PLUS', 'TLP',
            name='producttype', create_type=False,
        ), nullable=False),
        sa.Column('status', sa.Enum(
            'BOUND', 'ISSUED', 'CANCELLED', 'REINSTATED', name='policystatus'
        ), nullable=False),
        sa.Column('policy_number', sa.String(), nullable=False),
        sa.Column('inception_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('term_months', sa.Integer(), nullable=False),
        sa.Column('payment_type', sa.Enum(
            'CASH', 'FINANCE', name='paymenttype', create_type=False
        ), nullable=False),
        sa.Column('premium', sa.Numeric(10, 2), nullable=False),
        sa.Column('dealer_fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('broker_commission', sa.Numeric(10, 2), nullable=True),
        sa.Column('dealer_fee_rate', sa.Numeric(7, 4), nullable=True),
        sa.Column('broker_commission_rate', sa.Numeric(7, 4), nullable=True),
        sa.Column('policy_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('quote_id'),
        sa.UniqueConstraint('policy_number'),
    )
    op.create_index('ix_policies_id', 'policies', ['id'])
    op.create_index('ix_policies_policy_number', 'policies', ['policy_number'])

    op.create_table(
        'policy_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('policies.id'), nullable=False),
        sa.Column('transaction_type', sa.Enum(
            'BIND', 'ISSUE', 'ENDORSEMENT', 'CANCELLATION', 'REINSTATEMENT', name='transactiontype'
        ), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('premium_delta', sa.Numeric(10, 2), nullable=True),
        sa.Column('dealer_fee_delta', sa.Numeric(10, 2), nullable=True),
        sa.Column('broker_commission_delta', sa.Numeric(10, 2), nullable=True),
        sa.Column('dealer_fee_rate', sa.Numeric(7, 4), nullable=True),
        sa.Column('broker_commission_rate', sa.Numeric(7, 4), nullable=True),
        sa.Column('reason_code', sa.String(), nullable=True),
        sa.Column('reason_text', sa.Text(), nullable=True),
        sa.Column('snapshot', sa.JSON(), nullable=True),
    )
    op.create_index('ix_policy_transactions_id', 'policy_transactions', ['id'])

    op.create_table(
        'policy_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('policies.id'), nullable=False),
        sa.Column('document_type', sa.Enum(
            'POLICY_SCHEDULE', 'ENDORSEMENT_CERTIFICATE', 'CANCELLATION_NOTICE',
            'REINSTATEMENT_NOTICE', 'FINANCE_AGREEMENT', name='documenttype'
        ), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_policy_documents_id', 'policy_documents', ['id'])


def downgrade() -> None:
    op.drop_index('ix_policy_documents_id', table_name='policy_documents')
    op.drop_table('policy_documents')
    op.drop_index('ix_policy_transactions_id', table_name='policy_transactions')
    op.drop_table('policy_transactions')
    op.drop_index('ix_policies_policy_number', table_name='policies')
    op.drop_index('ix_policies_id', table_name='policies')
    op.drop_table('policies')
    op.drop_index('ix_vehicles_id', table_name='vehicles')
    op.drop_table('vehicles')
    op.drop_index('ix_quotes_id', table_name='quotes')
    op.drop_table('quotes')
    op.drop_index('ix_dealer_commissions_id', table_name='dealer_commissions')
    op.drop_table('dealer_commissions')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_dealers_id', table_name='dealers')
    op.drop_table('dealers')
    op.drop_index('ix_tenants_slug', table_name='tenants')
    op.drop_index('ix_tenants_id', table_name='tenants')
    op.drop_table('tenants')
    sa.Enum(name='documenttype').drop(op.get_bind())
    sa.Enum(name='transactiontype').drop(op.get_bind())
    sa.Enum(name='policystatus').drop(op.get_bind())
    sa.Enum(name='paymenttype').drop(op.get_bind())
    sa.Enum(name='quotestatus').drop(op.get_bind())
    sa.Enum(name='producttype').drop(op.get_bind())
    sa.Enum(name='commissiontype').drop(op.get_bind())
    sa.Enum(name='userrole').drop(op.get_bind())
