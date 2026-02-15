"""Provider search and detail routes."""

from flask import Blueprint, render_template, request

from app.models import (
    db, Provider, Address, ProviderTaxonomy, Spending,
    MvProviderSpendingSummary,
)

bp = Blueprint("providers", __name__)


@bp.route("/providers")
def provider_list():
    """Searchable/sortable provider rankings."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("q", "").strip()
    state = request.args.get("state", "").strip()
    sort = request.args.get("sort", "lifetime_paid")
    order = request.args.get("order", "desc")

    query = MvProviderSpendingSummary.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                MvProviderSpendingSummary.billing_npi.ilike(search_term),
                MvProviderSpendingSummary.organization_name.ilike(search_term),
                MvProviderSpendingSummary.last_name.ilike(search_term),
                MvProviderSpendingSummary.first_name.ilike(search_term),
            )
        )

    if state:
        query = query.filter(MvProviderSpendingSummary.state_code == state.upper())

    # Sorting
    sort_col = getattr(MvProviderSpendingSummary, sort, MvProviderSpendingSummary.lifetime_paid)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get distinct states for filter dropdown
    states = db.session.query(
        MvProviderSpendingSummary.state_code
    ).filter(
        MvProviderSpendingSummary.state_code.isnot(None)
    ).distinct().order_by(
        MvProviderSpendingSummary.state_code
    ).all()
    states = [s[0] for s in states]

    return render_template(
        "search.html",
        providers=pagination.items,
        pagination=pagination,
        search=search,
        state=state,
        sort=sort,
        order=order,
        states=states,
    )


@bp.route("/providers/<npi>")
def provider_detail(npi):
    """Single provider detail view."""
    provider = Provider.query.get_or_404(npi)
    addresses = Address.query.filter_by(npi=npi).all()
    taxonomies = ProviderTaxonomy.query.filter_by(npi=npi).all()

    # Monthly spending for this provider
    monthly_spending = db.session.query(
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

    # Top HCPCS codes for this provider
    top_hcpcs = db.session.query(
        Spending.hcpcs_code,
        db.func.sum(Spending.total_paid).label("total_paid"),
        db.func.sum(Spending.total_claims).label("total_claims"),
    ).filter(
        Spending.billing_npi == npi
    ).group_by(
        Spending.hcpcs_code
    ).order_by(
        db.func.sum(Spending.total_paid).desc()
    ).limit(20).all()

    # Summary stats
    summary = MvProviderSpendingSummary.query.get(npi)

    return render_template(
        "provider_detail.html",
        provider=provider,
        addresses=addresses,
        taxonomies=taxonomies,
        monthly_spending=monthly_spending,
        top_hcpcs=top_hcpcs,
        summary=summary,
    )
