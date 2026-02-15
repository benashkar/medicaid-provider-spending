"""JSON API endpoints for spending data (used by charts)."""

from flask import Blueprint, jsonify, request

from app.models import db, MvMonthlySpending, MvProviderSpendingSummary, Spending

bp = Blueprint("spending", __name__, url_prefix="/api")


@bp.route("/spending/monthly")
def monthly_spending():
    """Monthly spending time series for charts."""
    data = MvMonthlySpending.query.order_by(MvMonthlySpending.claim_month).all()

    return jsonify([
        {
            "month": row.claim_month.isoformat(),
            "total_paid": float(row.total_paid or 0),
            "total_claims": int(row.total_claims or 0),
            "active_providers": int(row.active_providers or 0),
            "total_benes": int(row.total_benes or 0),
        }
        for row in data
    ])


@bp.route("/providers/search")
def provider_search():
    """Provider search by name/NPI/state."""
    q = request.args.get("q", "").strip()
    state = request.args.get("state", "").strip()
    limit = request.args.get("limit", 20, type=int)

    query = MvProviderSpendingSummary.query

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            db.or_(
                MvProviderSpendingSummary.billing_npi.ilike(search_term),
                MvProviderSpendingSummary.organization_name.ilike(search_term),
                MvProviderSpendingSummary.last_name.ilike(search_term),
            )
        )

    if state:
        query = query.filter(MvProviderSpendingSummary.state_code == state.upper())

    results = query.order_by(
        MvProviderSpendingSummary.lifetime_paid.desc()
    ).limit(limit).all()

    return jsonify([
        {
            "npi": row.billing_npi.strip(),
            "name": row.display_name,
            "entity_type": row.entity_type,
            "state": row.state_code,
            "city": row.city,
            "lifetime_paid": float(row.lifetime_paid or 0),
            "lifetime_claims": int(row.lifetime_claims or 0),
        }
        for row in results
    ])


@bp.route("/providers/<npi>/spending")
def provider_spending(npi):
    """Per-provider spending time series."""
    data = db.session.query(
        Spending.claim_month,
        db.func.sum(Spending.total_paid).label("total_paid"),
        db.func.sum(Spending.total_claims).label("total_claims"),
        db.func.sum(Spending.total_unique_benes).label("total_benes"),
    ).filter(
        Spending.billing_npi == npi
    ).group_by(
        Spending.claim_month
    ).order_by(
        Spending.claim_month
    ).all()

    return jsonify([
        {
            "month": row.claim_month.isoformat(),
            "total_paid": float(row.total_paid or 0),
            "total_claims": int(row.total_claims or 0),
            "total_benes": int(row.total_benes or 0),
        }
        for row in data
    ])
