"""SQLAlchemy models for the Medicaid Provider Spending database (read-only)."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Provider(db.Model):
    __tablename__ = "providers"

    npi = db.Column(db.String(10), primary_key=True)
    entity_type = db.Column(db.SmallInteger, nullable=False)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    middle_name = db.Column(db.Text)
    credential = db.Column(db.Text)
    is_sole_proprietor = db.Column(db.Boolean)
    is_org_subpart = db.Column(db.Boolean)
    parent_org_name = db.Column(db.Text)
    parent_org_tin = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_phone = db.Column(db.Text)
    enumeration_date = db.Column(db.Date)
    last_update_date = db.Column(db.Date)
    deactivation_date = db.Column(db.Date)
    reactivation_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True))

    addresses = db.relationship("Address", backref="provider", lazy="select")
    taxonomies = db.relationship("ProviderTaxonomy", backref="provider", lazy="select")

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p)
        if self.credential:
            name += f", {self.credential}"
        return name or self.npi


class Address(db.Model):
    __tablename__ = "addresses"

    address_id = db.Column(db.Integer, primary_key=True)
    npi = db.Column(db.String(10), db.ForeignKey("providers.npi"), nullable=False)
    address_purpose = db.Column(db.Text, nullable=False)
    street_line_1 = db.Column(db.Text)
    street_line_2 = db.Column(db.Text)
    city = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    zip5 = db.Column(db.String(5))
    zip4 = db.Column(db.String(4))
    country_code = db.Column(db.String(2))
    phone = db.Column(db.Text)
    fax = db.Column(db.Text)
    street_number = db.Column(db.Text)
    street_name = db.Column(db.Text)
    street_suffix = db.Column(db.Text)
    unit_type = db.Column(db.Text)
    unit_number = db.Column(db.Text)

    @property
    def full_address(self):
        parts = [self.street_line_1]
        if self.street_line_2:
            parts.append(self.street_line_2)
        city_state = ", ".join(p for p in [self.city, self.state_code] if p)
        if city_state:
            parts.append(city_state)
        if self.zip5:
            parts.append(self.zip5)
        return ", ".join(parts)


class ProviderTaxonomy(db.Model):
    __tablename__ = "provider_taxonomies"

    id = db.Column(db.Integer, primary_key=True)
    npi = db.Column(db.String(10), db.ForeignKey("providers.npi"), nullable=False)
    taxonomy_code = db.Column(db.Text, nullable=False)
    license_number = db.Column(db.Text)
    license_state = db.Column(db.String(2))
    is_primary = db.Column(db.Boolean, default=False)


class HcpcsCode(db.Model):
    __tablename__ = "hcpcs_codes"

    hcpcs_code = db.Column(db.Text, primary_key=True)
    short_description = db.Column(db.Text)
    long_description = db.Column(db.Text)
    category = db.Column(db.Text)


class Spending(db.Model):
    __tablename__ = "spending"

    id = db.Column(db.BigInteger, primary_key=True)
    billing_npi = db.Column(db.String(10), nullable=False)
    servicing_npi = db.Column(db.String(10), nullable=False)
    hcpcs_code = db.Column(db.Text, nullable=False)
    claim_month = db.Column(db.Date, nullable=False)
    total_unique_benes = db.Column(db.Integer)
    total_claims = db.Column(db.Integer)
    total_paid = db.Column(db.Numeric(15, 2))


# Materialized view models (read-only)

class MvProviderSpendingSummary(db.Model):
    __tablename__ = "mv_provider_spending_summary"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    entity_type = db.Column(db.SmallInteger)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    zip5 = db.Column(db.String(5))
    total_rows = db.Column(db.BigInteger)
    lifetime_claims = db.Column(db.BigInteger)
    lifetime_paid = db.Column(db.Numeric)
    lifetime_benes = db.Column(db.BigInteger)
    first_claim_month = db.Column(db.Date)
    last_claim_month = db.Column(db.Date)
    distinct_hcpcs_codes = db.Column(db.BigInteger)

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.billing_npi


class MvMonthlySpending(db.Model):
    __tablename__ = "mv_monthly_spending"
    __table_args__ = {"info": {"is_view": True}}

    claim_month = db.Column(db.Date, primary_key=True)
    active_providers = db.Column(db.BigInteger)
    total_claims = db.Column(db.BigInteger)
    total_paid = db.Column(db.Numeric)
    total_benes = db.Column(db.BigInteger)


class MvStateSpending(db.Model):
    __tablename__ = "mv_state_spending"
    __table_args__ = {"info": {"is_view": True}}

    state_code = db.Column(db.String(2), primary_key=True)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    provider_count = db.Column(db.BigInteger)
    total_benes = db.Column(db.BigInteger)


class MvHcpcsSpending(db.Model):
    __tablename__ = "mv_hcpcs_spending"
    __table_args__ = {"info": {"is_view": True}}

    hcpcs_code = db.Column(db.Text, primary_key=True)
    short_description = db.Column(db.Text)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    provider_count = db.Column(db.BigInteger)
