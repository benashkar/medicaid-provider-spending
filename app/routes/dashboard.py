"""Main dashboard routes."""

from flask import Blueprint, render_template

from app.models import db, MvMonthlySpending, MvProviderSpendingSummary, MvStateSpending

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    """Dashboard home with KPI cards."""
    # Aggregate KPIs from materialized views
    monthly = db.session.query(
        db.func.sum(MvMonthlySpending.total_paid).label("total_paid"),
        db.func.sum(MvMonthlySpending.total_claims).label("total_claims"),
        db.func.sum(MvMonthlySpending.total_benes).label("total_benes"),
        db.func.min(MvMonthlySpending.claim_month).label("min_date"),
        db.func.max(MvMonthlySpending.claim_month).label("max_date"),
    ).first()

    provider_count = db.session.query(
        db.func.count(MvProviderSpendingSummary.billing_npi)
    ).scalar() or 0

    state_count = db.session.query(
        db.func.count(MvStateSpending.state_code)
    ).scalar() or 0

    return render_template(
        "dashboard.html",
        total_paid=monthly.total_paid or 0,
        total_claims=monthly.total_claims or 0,
        total_benes=monthly.total_benes or 0,
        provider_count=provider_count,
        state_count=state_count,
        date_min=monthly.min_date,
        date_max=monthly.max_date,
    )


@bp.route("/trends")
def trends():
    """Spending trends over time."""
    monthly_data = MvMonthlySpending.query.order_by(
        MvMonthlySpending.claim_month
    ).all()

    return render_template("spending_trends.html", monthly_data=monthly_data)


@bp.route("/geographic")
def geographic():
    """Geographic spending view."""
    state_data = MvStateSpending.query.order_by(
        MvStateSpending.total_paid.desc()
    ).all()

    return render_template("geographic.html", state_data=state_data)


@bp.route("/hcpcs")
def hcpcs():
    """HCPCS procedure code spending."""
    from app.models import MvHcpcsSpending
    hcpcs_data = MvHcpcsSpending.query.order_by(
        MvHcpcsSpending.total_paid.desc()
    ).limit(100).all()

    return render_template("hcpcs.html", hcpcs_data=hcpcs_data)
