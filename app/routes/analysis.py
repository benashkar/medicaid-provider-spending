"""Analysis routes for advanced spending views."""

from flask import Blueprint, render_template, request

from app.models import (
    db, MvTopOrganizations, MvSpendingGrowth, MvOutlierProviders,
    MvGeographicConcentration, MvBillingServicingNetwork,
)

bp = Blueprint("analysis", __name__, url_prefix="/analysis")


@bp.route("/")
def index():
    """Analysis overview page."""
    return render_template("analysis/index.html")


@bp.route("/top-organizations")
def top_organizations():
    """Top 100 organizations by lifetime spending."""
    orgs = MvTopOrganizations.query.order_by(
        MvTopOrganizations.lifetime_paid.desc()
    ).limit(100).all()
    return render_template("analysis/top_organizations.html", orgs=orgs)


@bp.route("/spending-growth")
def spending_growth():
    """Month-over-month spending growth anomalies (>100% increase)."""
    page = request.args.get("page", 1, type=int)
    query = MvSpendingGrowth.query.order_by(
        MvSpendingGrowth.pct_change.desc()
    )
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "analysis/spending_growth.html",
        items=pagination.items,
        pagination=pagination,
    )


@bp.route("/outliers")
def outlier_providers():
    """Providers with spending >2 std dev above peer mean per HCPCS code."""
    page = request.args.get("page", 1, type=int)
    query = MvOutlierProviders.query.order_by(
        MvOutlierProviders.z_score.desc()
    )
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "analysis/outliers.html",
        items=pagination.items,
        pagination=pagination,
    )


@bp.route("/geographic")
def geographic_concentration():
    """Geographic concentration by ZIP code."""
    state = request.args.get("state", "").strip()
    query = MvGeographicConcentration.query

    if state:
        query = query.filter(MvGeographicConcentration.state_code == state.upper())

    query = query.order_by(MvGeographicConcentration.total_paid.desc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    # Get states for filter
    states = db.session.query(
        MvGeographicConcentration.state_code
    ).distinct().order_by(
        MvGeographicConcentration.state_code
    ).all()
    states = [s[0] for s in states]

    return render_template(
        "analysis/geographic_concentration.html",
        items=pagination.items,
        pagination=pagination,
        state=state,
        states=states,
    )


@bp.route("/network")
def billing_network():
    """Billing vs servicing provider relationship network."""
    npi = request.args.get("npi", "").strip()
    query = MvBillingServicingNetwork.query

    if npi:
        query = query.filter(
            db.or_(
                MvBillingServicingNetwork.billing_npi == npi,
                MvBillingServicingNetwork.servicing_npi == npi,
            )
        )

    query = query.order_by(MvBillingServicingNetwork.total_paid.desc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "analysis/network.html",
        items=pagination.items,
        pagination=pagination,
        npi=npi,
    )
