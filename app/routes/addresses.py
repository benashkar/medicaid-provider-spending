"""Address analysis routes."""

from flask import Blueprint, render_template

from app.models import db, Address

bp = Blueprint("addresses", __name__)


@bp.route("/addresses")
def address_analysis():
    """Address analysis: shared addresses, normalization quality."""
    # Providers sharing the same practice address
    shared_addresses = db.session.query(
        Address.street_line_1,
        Address.city,
        Address.state_code,
        Address.zip5,
        db.func.count(Address.npi).label("provider_count"),
        db.func.array_agg(Address.npi).label("npis"),
    ).filter(
        Address.address_purpose == "PRACTICE",
        Address.street_line_1.isnot(None),
    ).group_by(
        Address.street_line_1,
        Address.city,
        Address.state_code,
        Address.zip5,
    ).having(
        db.func.count(Address.npi) > 3
    ).order_by(
        db.func.count(Address.npi).desc()
    ).limit(100).all()

    # Normalization quality stats
    total_addresses = db.session.query(db.func.count(Address.address_id)).scalar() or 0
    parsed_count = db.session.query(
        db.func.count(Address.address_id)
    ).filter(Address.street_number.isnot(None)).scalar() or 0

    parse_rate = round(parsed_count / total_addresses * 100, 1) if total_addresses else 0

    return render_template(
        "addresses.html",
        shared_addresses=shared_addresses,
        total_addresses=total_addresses,
        parsed_count=parsed_count,
        parse_rate=parse_rate,
    )
