"""
[EN] Analysis routes for advanced spending views.
     Provides pages for deeper Medicare spending analysis including:
     top organizations by spending, month-over-month spending growth anomalies,
     statistical outlier detection, geographic concentration by ZIP code,
     and billing-servicing provider network relationships.

[RU] Маршруты анализа для расширенных представлений расходов.
     Предоставляет страницы для углублённого анализа расходов Medicare, включая:
     топ-организации по расходам, аномалии роста расходов от месяца к месяцу,
     статистическое обнаружение выбросов, географическую концентрацию по почтовым индексам
     и сетевые связи между выставляющими счета и обслуживающими поставщиками.

[PT] Rotas de análise para visualizações avançadas de gastos.
     Fornece páginas para análise aprofundada de gastos do Medicare, incluindo:
     principais organizações por gastos, anomalias de crescimento mensal,
     detecção estatística de outliers, concentração geográfica por CEP
     e relacionamentos de rede entre provedores faturadores e atendentes.
"""

from flask import Blueprint, render_template, request

from app.models import (
    db, MvTopOrganizations, MvSpendingGrowth, MvOutlierProviders,
    MvGeographicConcentration, MvBillingServicingNetwork,
    MvOrgYoyGrowth, MvAddressClustering, MvRapidRamp, MvFraudRiskScore,
    MvAvgClaimByProvider, MvOfficialNetwork,
)

# [EN] Create the "analysis" blueprint with URL prefix "/analysis" — all routes start with /analysis/...
# [RU] Создать блюпринт «analysis» с префиксом URL "/analysis" — все маршруты начинаются с /analysis/...
# [PT] Criar o blueprint "analysis" com prefixo de URL "/analysis" — todas as rotas começam com /analysis/...
bp = Blueprint("analysis", __name__, url_prefix="/analysis")


# [EN] Analysis overview page ("/analysis/") — landing page with links to all analysis sub-pages.
# [RU] Обзорная страница анализа ("/analysis/") — страница со ссылками на все подстраницы анализа.
# [PT] Página de visão geral da análise ("/analysis/") — página com links para todas as sub-páginas de análise.
@bp.route("/")
def index():
    """Analysis overview page."""
    return render_template("analysis/index.html")


# [EN] Top organizations page ("/analysis/top-organizations") — ranks the top 100 organizations
#      by lifetime total spending. Useful for identifying the largest Medicare spenders.
# [RU] Страница топ-организаций ("/analysis/top-organizations") — ранжирует 100 организаций
#      по общему объёму расходов за всё время. Полезно для выявления крупнейших получателей средств Medicare.
# [PT] Página de principais organizações ("/analysis/top-organizations") — classifica as 100 organizações
#      com maiores gastos acumulados. Útil para identificar os maiores gastadores do Medicare.
@bp.route("/top-organizations")
def top_organizations():
    """Top 100 organizations by lifetime spending."""
    orgs = MvTopOrganizations.query.order_by(
        MvTopOrganizations.lifetime_paid.desc()
    ).limit(100).all()
    return render_template("analysis/top_organizations.html", orgs=orgs)


# [EN] Spending growth page ("/analysis/spending-growth") — identifies providers with large
#      month-over-month payment increases (>100%). Paginated, sorted by percentage change descending.
#      These spikes may indicate billing anomalies or changes in provider activity.
# [RU] Страница роста расходов ("/analysis/spending-growth") — выявляет поставщиков с большим
#      ростом выплат от месяца к месяцу (>100%). С пагинацией, сортировка по убыванию процентного изменения.
#      Такие скачки могут указывать на аномалии биллинга или изменения в деятельности поставщика.
# [PT] Página de crescimento de gastos ("/analysis/spending-growth") — identifica provedores com grandes
#      aumentos mensais de pagamento (>100%). Paginado, ordenado por variação percentual decrescente.
#      Esses picos podem indicar anomalias de faturamento ou mudanças na atividade do provedor.
@bp.route("/spending-growth")
def spending_growth():
    """Year-over-year spending growth with filterable year range and % threshold."""
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "dollar")  # "dollar" or "pct"
    min_pct = request.args.get("min_pct", "", type=str).strip()
    year_from = request.args.get("year_from", "", type=str).strip()
    year_to = request.args.get("year_to", "", type=str).strip()
    state = request.args.get("state", "").strip()
    entity = request.args.get("entity", "", type=str).strip()

    query = MvSpendingGrowth.query

    if min_pct:
        query = query.filter(MvSpendingGrowth.pct_change >= float(min_pct))
    if year_from:
        query = query.filter(MvSpendingGrowth.claim_year >= int(year_from))
    if year_to:
        query = query.filter(MvSpendingGrowth.claim_year <= int(year_to))
    if state:
        query = query.filter(MvSpendingGrowth.state_code == state.upper())
    if entity in ("1", "2"):
        query = query.filter(MvSpendingGrowth.entity_type == int(entity))

    if sort == "pct":
        query = query.order_by(MvSpendingGrowth.pct_change.desc())
    else:
        query = query.order_by(MvSpendingGrowth.dollar_change.desc())

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    years = db.session.query(
        MvSpendingGrowth.claim_year
    ).distinct().order_by(MvSpendingGrowth.claim_year.desc()).all()
    years = [y[0] for y in years]

    states = db.session.query(
        MvSpendingGrowth.state_code
    ).distinct().order_by(MvSpendingGrowth.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/spending_growth.html",
        items=pagination.items,
        pagination=pagination,
        sort=sort,
        min_pct=min_pct,
        year_from=year_from,
        year_to=year_to,
        state=state,
        entity=entity,
        years=years,
        states=states,
    )


# [EN] Outlier providers page ("/analysis/outliers") — shows providers whose spending on a specific
#      HCPCS code is more than 2 standard deviations above the peer group mean.
#      Sorted by z-score descending (most anomalous first). Paginated.
# [RU] Страница аномальных поставщиков ("/analysis/outliers") — показывает поставщиков, чьи расходы
#      по конкретному коду HCPCS превышают среднее по группе более чем на 2 стандартных отклонения.
#      Сортировка по z-оценке по убыванию (наиболее аномальные первыми). С пагинацией.
# [PT] Página de provedores atípicos ("/analysis/outliers") — mostra provedores cujos gastos em um
#      código HCPCS específico excedem a média do grupo em mais de 2 desvios padrão.
#      Ordenado por z-score decrescente (mais anômalos primeiro). Paginado.
@bp.route("/outliers")
def outlier_providers():
    """Providers with spending >2 std dev above peer mean per HCPCS code."""
    page = request.args.get("page", 1, type=int)
    # [EN] Query outlier records sorted by z-score (highest statistical deviation first)
    # [RU] Запросить записи о выбросах, отсортированные по z-оценке (наибольшее статистическое отклонение первым)
    # [PT] Consultar registros de outliers ordenados por z-score (maior desvio estatístico primeiro)
    query = MvOutlierProviders.query.order_by(
        MvOutlierProviders.z_score.desc()
    )
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "analysis/outliers.html",
        items=pagination.items,
        pagination=pagination,
    )


# [EN] Geographic concentration page ("/analysis/geographic") — shows spending density by ZIP code.
#      Supports optional state filter. Paginated, sorted by total_paid descending.
#      Helps identify geographic hotspots of Medicare spending.
# [RU] Страница географической концентрации ("/analysis/geographic") — показывает плотность расходов по почтовым индексам.
#      Поддерживает необязательный фильтр по штату. С пагинацией, сортировка по total_paid по убыванию.
#      Помогает выявить географические очаги расходов Medicare.
# [PT] Página de concentração geográfica ("/analysis/geographic") — mostra a densidade de gastos por CEP.
#      Suporta filtro opcional por estado. Paginado, ordenado por total_paid decrescente.
#      Ajuda a identificar hotspots geográficos de gastos do Medicare.
@bp.route("/geographic")
def geographic_concentration():
    """Geographic concentration by ZIP code."""
    state = request.args.get("state", "").strip()
    query = MvGeographicConcentration.query

    # [EN] If a state is specified, filter results to that state only
    # [RU] Если указан штат, фильтровать результаты только по этому штату
    # [PT] Se um estado for especificado, filtrar resultados apenas para esse estado
    if state:
        query = query.filter(MvGeographicConcentration.state_code == state.upper())

    query = query.order_by(MvGeographicConcentration.total_paid.desc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    # [EN] Get distinct state codes for the dropdown filter in the UI
    # [RU] Получить уникальные коды штатов для выпадающего фильтра в интерфейсе
    # [PT] Obter códigos de estado distintos para o filtro dropdown na interface
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


# [EN] Billing network page ("/analysis/network") — shows relationships between billing and servicing providers.
#      A billing provider submits claims; a servicing provider performs the service.
#      Supports optional NPI filter to show connections for a specific provider.
#      Sorted by total_paid descending. Paginated.
# [RU] Страница сети биллинга ("/analysis/network") — показывает связи между выставляющими счета и обслуживающими поставщиками.
#      Выставляющий счета подаёт заявки; обслуживающий поставщик оказывает услугу.
#      Поддерживает необязательный фильтр по NPI для отображения связей конкретного поставщика.
#      Сортировка по total_paid по убыванию. С пагинацией.
# [PT] Página de rede de faturamento ("/analysis/network") — mostra relacionamentos entre provedores faturadores e atendentes.
#      O provedor faturador submete sinistros; o provedor atendente realiza o serviço.
#      Suporta filtro opcional por NPI para mostrar conexões de um provedor específico.
#      Ordenado por total_paid decrescente. Paginado.
@bp.route("/network")
def billing_network():
    """Billing vs servicing provider relationship network."""
    npi = request.args.get("npi", "").strip()
    query = MvBillingServicingNetwork.query

    # [EN] If an NPI is specified, filter to show only relationships where that NPI
    #      appears as either the billing or the servicing provider
    # [RU] Если указан NPI, фильтровать, чтобы показать только связи, где этот NPI
    #      выступает в роли выставляющего счета или обслуживающего поставщика
    # [PT] Se um NPI for especificado, filtrar para mostrar apenas relacionamentos onde esse NPI
    #      aparece como provedor faturador ou atendente
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


# =============================================================================
# [EN] FRAUD DETECTION ROUTES — Year-over-year growth, address clustering,
#      rapid ramp detection, and composite fraud risk scoring.
# [RU] МАРШРУТЫ ОБНАРУЖЕНИЯ МОШЕННИЧЕСТВА — Рост год к году, кластеризация адресов,
#      обнаружение быстрого роста и комплексная оценка риска мошенничества.
# [PT] ROTAS DE DETECÇÃO DE FRAUDE — Crescimento ano a ano, clustering de endereços,
#      detecção de rampa rápida e pontuação composta de risco de fraude.
# =============================================================================


@bp.route("/yoy-growth")
def yoy_growth():
    """Year-over-year organization spending growth with filterable year range."""
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "dollar")  # "dollar" or "pct"
    year = request.args.get("year", "", type=str).strip()
    state = request.args.get("state", "").strip()

    query = MvOrgYoyGrowth.query

    if year:
        query = query.filter(MvOrgYoyGrowth.claim_year == int(year))
    if state:
        query = query.filter(MvOrgYoyGrowth.state_code == state.upper())

    if sort == "pct":
        query = query.order_by(MvOrgYoyGrowth.pct_increase.desc())
    else:
        query = query.order_by(MvOrgYoyGrowth.dollar_increase.desc())

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    # Get available years and states for filter dropdowns
    years = db.session.query(
        MvOrgYoyGrowth.claim_year
    ).distinct().order_by(MvOrgYoyGrowth.claim_year.desc()).all()
    years = [y[0] for y in years]

    states = db.session.query(
        MvOrgYoyGrowth.state_code
    ).distinct().order_by(MvOrgYoyGrowth.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/yoy_growth.html",
        items=pagination.items,
        pagination=pagination,
        sort=sort,
        year=year,
        state=state,
        years=years,
        states=states,
    )


@bp.route("/address-clustering")
def address_clustering():
    """Same-building address clustering for fraud detection."""
    page = request.args.get("page", 1, type=int)
    state = request.args.get("state", "").strip()
    min_providers = request.args.get("min_providers", 2, type=int)

    query = MvAddressClustering.query

    if state:
        query = query.filter(MvAddressClustering.state_code == state.upper())
    if min_providers > 2:
        query = query.filter(MvAddressClustering.provider_count >= min_providers)

    query = query.order_by(MvAddressClustering.combined_spending.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    states = db.session.query(
        MvAddressClustering.state_code
    ).distinct().order_by(MvAddressClustering.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/address_clustering.html",
        items=pagination.items,
        pagination=pagination,
        state=state,
        states=states,
        min_providers=min_providers,
    )


@bp.route("/rapid-ramp")
def rapid_ramp():
    """Recently registered organizations with fast spending growth."""
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "paid")  # "paid" or "speed"
    state = request.args.get("state", "").strip()

    query = MvRapidRamp.query

    if state:
        query = query.filter(MvRapidRamp.state_code == state.upper())

    if sort == "speed":
        # Fastest ramp = highest average monthly spend
        query = query.order_by(MvRapidRamp.avg_monthly_spend.desc())
    else:
        query = query.order_by(MvRapidRamp.lifetime_paid.desc())

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    states = db.session.query(
        MvRapidRamp.state_code
    ).distinct().order_by(MvRapidRamp.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/rapid_ramp.html",
        items=pagination.items,
        pagination=pagination,
        sort=sort,
        state=state,
        states=states,
    )


# [EN] Entity designation categories for organization name filtering.
#      Categorized into "suspicious" (shell company / provider mill indicators)
#      and "legitimate" (established institutions / standard professional corps).
#      The top-level "suspicious" and "legitimate" keys combine all patterns
#      in their respective category for a single-click aggregate filter.
# [RU] Категории юридических форм для фильтрации названий организаций.
#      Разделены на «подозрительные» (индикаторы подставных компаний) и
#      «легитимные» (устоявшиеся учреждения / стандартные профессиональные корпорации).
# [PT] Categorias de designacao de entidade para filtragem de nomes de organizacoes.
#      Categorizados em "suspeitos" (indicadores de empresas de fachada)
#      e "legitimos" (instituicoes estabelecidas / corporacoes profissionais padrao).

# [EN] Suspicious entity types — common in shell companies, provider mills, DME fraud
# [RU] Подозрительные типы — распространены в подставных компаниях, мошенничестве с DME
# [PT] Tipos suspeitos — comuns em empresas de fachada, fraude com DME
SUSPICIOUS_ENTITY_FILTERS = {
    "llc": {"label": "LLC / PLLC / LLP", "patterns": ["LLC", "PLLC", "LLP"]},
    "enterprise": {
        "label": "Enterprise / Holdings / Management",
        "patterns": ["ENTERPRISE", "ENTERPRISES", "HOLDINGS", "MANAGEMENT"],
    },
    "solutions": {
        "label": "Solutions / Consulting",
        "patterns": ["SOLUTIONS", "CONSULTING"],
    },
    "staffing": {
        "label": "Staffing / Agency",
        "patterns": ["STAFFING", "AGENCY"],
    },
    "supply": {
        "label": "Supply / Supplies (DME)",
        "patterns": ["SUPPLY", "SUPPLIES"],
    },
    "wellness": {
        "label": "Wellness / Global / International",
        "patterns": ["WELLNESS", "GLOBAL", "INTERNATIONAL"],
    },
}

# [EN] Legitimate entity types — established institutions, health systems, standard professional corps
# [RU] Легитимные типы — устоявшиеся учреждения, системы здравоохранения, стандартные профессиональные корпорации
# [PT] Tipos legitimos — instituicoes estabelecidas, sistemas de saude, corporacoes profissionais padrao
LEGITIMATE_ENTITY_FILTERS = {
    "hospital": {
        "label": "Hospital / Community / Foundation / Center",
        "patterns": ["HOSPITAL", "COMMUNITY", "FOUNDATION", "CENTER"],
    },
    "corp": {"label": "Inc / Corp", "patterns": ["INC", "CORP", "CORPORATION"]},
    "pc_pa": {"label": "PC / PA (Professional)", "patterns": ["PC", "PA"]},
}

# [EN] Combined lookup for route logic — maps every individual key plus the aggregate keys
# [RU] Объединённый словарь для логики маршрута
# [PT] Dicionario combinado para logica de rota
ORG_DESIGNATION_FILTERS = {
    **SUSPICIOUS_ENTITY_FILTERS,
    **LEGITIMATE_ENTITY_FILTERS,
}

# [EN] Aggregate keys that combine all patterns from their category
# [RU] Агрегатные ключи, объединяющие все шаблоны из своей категории
# [PT] Chaves agregadas que combinam todos os padroes de sua categoria
ALL_SUSPICIOUS_PATTERNS = []
for v in SUSPICIOUS_ENTITY_FILTERS.values():
    ALL_SUSPICIOUS_PATTERNS.extend(v["patterns"])

ALL_LEGITIMATE_PATTERNS = []
for v in LEGITIMATE_ENTITY_FILTERS.values():
    ALL_LEGITIMATE_PATTERNS.extend(v["patterns"])


@bp.route("/fraud-risk")
def fraud_risk():
    """Composite fraud risk score dashboard — organizations ranked by number of flags."""
    page = request.args.get("page", 1, type=int)
    min_score = request.args.get("min_score", 1, type=int)
    state = request.args.get("state", "").strip()
    org_type = request.args.get("org_type", "").strip()

    query = MvFraudRiskScore.query.filter(MvFraudRiskScore.risk_score >= min_score)

    if state:
        query = query.filter(MvFraudRiskScore.state_code == state.upper())

    # [EN] Filter by organization entity designation (name patterns).
    #      Supports individual category keys (e.g., "llc", "staffing") and
    #      aggregate keys ("suspicious" = all suspicious, "legitimate" = all legitimate).
    # [RU] Фильтрация по юридической форме организации (шаблоны названий).
    #      Поддерживает отдельные ключи категорий и агрегатные ключи.
    # [PT] Filtragem por designacao da entidade (padroes de nome).
    #      Suporta chaves de categoria individuais e chaves agregadas.
    if org_type:
        # [EN] Determine which patterns to match based on filter key
        # [RU] Определяем, какие шаблоны сопоставлять на основе ключа фильтра
        # [PT] Determina quais padroes corresponder com base na chave do filtro
        if org_type == "suspicious":
            patterns = ALL_SUSPICIOUS_PATTERNS
        elif org_type == "legitimate":
            patterns = ALL_LEGITIMATE_PATTERNS
        elif org_type in ORG_DESIGNATION_FILTERS:
            patterns = ORG_DESIGNATION_FILTERS[org_type]["patterns"]
        else:
            patterns = []

        if patterns:
            conditions = []
            for pat in patterns:
                # [EN] Match word boundary: " LLC", " LLC,", " LLC.", start with "LLC "
                # [RU] Сопоставление границы слова
                # [PT] Correspondencia de limite de palavra
                conditions.append(
                    MvFraudRiskScore.organization_name.ilike(f"% {pat}")
                )
                conditions.append(
                    MvFraudRiskScore.organization_name.ilike(f"% {pat},%")
                )
                conditions.append(
                    MvFraudRiskScore.organization_name.ilike(f"% {pat}.%")
                )
                conditions.append(
                    MvFraudRiskScore.organization_name.ilike(f"{pat} %")
                )
            query = query.filter(db.or_(*conditions))

    query = query.order_by(
        MvFraudRiskScore.risk_score.desc(),
        MvFraudRiskScore.lifetime_paid.desc(),
    )

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    states = db.session.query(
        MvFraudRiskScore.state_code
    ).distinct().order_by(MvFraudRiskScore.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/fraud_risk.html",
        items=pagination.items,
        pagination=pagination,
        min_score=min_score,
        state=state,
        states=states,
        org_type=org_type,
        suspicious_filters=SUSPICIOUS_ENTITY_FILTERS,
        legitimate_filters=LEGITIMATE_ENTITY_FILTERS,
    )


@bp.route("/avg-claim")
def avg_claim():
    """Average claim amount by provider — sortable highest/lowest, filterable by state/type."""
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "highest")  # "highest" or "lowest"
    state = request.args.get("state", "").strip()
    entity = request.args.get("entity", "", type=str).strip()  # "1" or "2" or ""

    query = MvAvgClaimByProvider.query

    if state:
        query = query.filter(MvAvgClaimByProvider.state_code == state.upper())
    if entity in ("1", "2"):
        query = query.filter(MvAvgClaimByProvider.entity_type == int(entity))

    if sort == "lowest":
        query = query.order_by(MvAvgClaimByProvider.avg_claim_amount.asc())
    else:
        query = query.order_by(MvAvgClaimByProvider.avg_claim_amount.desc())

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    states = db.session.query(
        MvAvgClaimByProvider.state_code
    ).distinct().order_by(MvAvgClaimByProvider.state_code).all()
    states = [s[0] for s in states if s[0]]

    return render_template(
        "analysis/avg_claim.html",
        items=pagination.items,
        pagination=pagination,
        sort=sort,
        state=state,
        entity=entity,
        states=states,
    )


@bp.route("/official-network")
def official_network():
    """Authorized officials controlling multiple organizations — fraud indicator."""
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "count")  # "count" or "spending"
    min_orgs = request.args.get("min_orgs", 2, type=int)

    query = MvOfficialNetwork.query

    if min_orgs > 2:
        query = query.filter(MvOfficialNetwork.org_count >= min_orgs)

    if sort == "spending":
        query = query.order_by(MvOfficialNetwork.combined_spending.desc())
    else:
        query = query.order_by(
            MvOfficialNetwork.org_count.desc(),
            MvOfficialNetwork.combined_spending.desc(),
        )

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "analysis/official_network.html",
        items=pagination.items,
        pagination=pagination,
        sort=sort,
        min_orgs=min_orgs,
    )
