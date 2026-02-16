"""
[EN] Main dashboard routes — serves the home page with KPI cards,
     spending trends over time, geographic breakdown, and HCPCS procedure spending.
     All data comes from pre-aggregated materialized views for fast page loads.

[RU] Маршруты главной панели — отображает главную страницу с KPI-карточками,
     тренды расходов во времени, географическое распределение и расходы по процедурам HCPCS.
     Все данные берутся из предварительно агрегированных материализованных представлений для быстрой загрузки.

[PT] Rotas do painel principal — exibe a página inicial com cartões de KPI,
     tendências de gastos ao longo do tempo, distribuição geográfica e gastos por procedimentos HCPCS.
     Todos os dados vêm de views materializadas pré-agregadas para carregamento rápido.
"""

from flask import Blueprint, render_template, request

from app.models import db, MvMonthlySpending, MvProviderSpendingSummary, MvStateSpending

# [EN] Create the "dashboard" blueprint — all routes in this file are registered under it
# [RU] Создать блюпринт «dashboard» — все маршруты в этом файле регистрируются в нём
# [PT] Criar o blueprint "dashboard" — todas as rotas neste arquivo são registradas nele
bp = Blueprint("dashboard", __name__)


# [EN] Dashboard home page (root URL "/") — displays high-level KPI summary cards.
#      Shows total paid, total claims, total beneficiaries, provider count, state count, and date range.
# [RU] Главная страница панели (корневой URL "/") — отображает обзорные KPI-карточки.
#      Показывает общую сумму выплат, количество заявок, получателей, поставщиков, штатов и диапазон дат.
# [PT] Página inicial do painel (URL raiz "/") — exibe cartões resumidos de KPI.
#      Mostra total pago, total de sinistros, beneficiários, provedores, estados e período de datas.
@bp.route("/")
def index():
    """Dashboard home with KPI cards."""
    # [EN] Query the monthly spending view to get aggregate totals (SUM) and date range (MIN/MAX)
    # [RU] Запрос к представлению ежемесячных расходов для получения агрегированных сумм (SUM) и диапазона дат (MIN/MAX)
    # [PT] Consulta à view de gastos mensais para obter totais agregados (SUM) e intervalo de datas (MIN/MAX)
    monthly = db.session.query(
        db.func.sum(MvMonthlySpending.total_paid).label("total_paid"),
        db.func.sum(MvMonthlySpending.total_claims).label("total_claims"),
        db.func.sum(MvMonthlySpending.total_benes).label("total_benes"),
        db.func.min(MvMonthlySpending.claim_month).label("min_date"),
        db.func.max(MvMonthlySpending.claim_month).label("max_date"),
    ).first()

    # [EN] Count distinct billing providers across all records
    # [RU] Подсчитать количество уникальных поставщиков среди всех записей
    # [PT] Contar provedores de faturamento distintos em todos os registros
    provider_count = db.session.query(
        db.func.count(MvProviderSpendingSummary.billing_npi)
    ).scalar() or 0

    # [EN] Count distinct states with spending data
    # [RU] Подсчитать количество штатов с данными о расходах
    # [PT] Contar estados distintos com dados de gastos
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


# [EN] Spending trends page ("/trends") — shows a time-series chart of monthly spending.
#      Data is sorted chronologically so charts can plot it directly.
# [RU] Страница трендов расходов ("/trends") — показывает график расходов по месяцам.
#      Данные отсортированы хронологически, чтобы графики могли использовать их напрямую.
# [PT] Página de tendências de gastos ("/trends") — mostra um gráfico de gastos mensais.
#      Os dados são ordenados cronologicamente para que os gráficos possam plotá-los diretamente.
@bp.route("/trends")
def trends():
    """Spending trends over time."""
    monthly_data = MvMonthlySpending.query.order_by(
        MvMonthlySpending.claim_month
    ).all()

    return render_template("spending_trends.html", monthly_data=monthly_data)


# [EN] Geographic spending page ("/geographic") — displays spending breakdown by US state.
#      States are sorted by total_paid descending (highest spending first).
# [RU] Страница географии расходов ("/geographic") — показывает распределение расходов по штатам США.
#      Штаты отсортированы по total_paid по убыванию (сначала наибольшие расходы).
# [PT] Página de gastos geográficos ("/geographic") — exibe a distribuição de gastos por estado dos EUA.
#      Os estados são ordenados por total_paid decrescente (maiores gastos primeiro).
@bp.route("/geographic")
def geographic():
    """Geographic spending view."""
    state_data = MvStateSpending.query.order_by(
        MvStateSpending.total_paid.desc()
    ).all()

    return render_template("geographic.html", state_data=state_data)


# [EN] HCPCS procedure spending page ("/hcpcs") — shows top 100 procedure codes by total spending.
#      HCPCS = Healthcare Common Procedure Coding System (medical billing codes).
# [RU] Страница расходов по процедурам HCPCS ("/hcpcs") — показывает 100 кодов процедур с наибольшими расходами.
#      HCPCS = Система кодирования медицинских процедур (коды медицинского биллинга).
# [PT] Página de gastos por procedimentos HCPCS ("/hcpcs") — mostra os 100 códigos de procedimento com maiores gastos.
#      HCPCS = Sistema de Codificação de Procedimentos Médicos (códigos de faturamento médico).
@bp.route("/hcpcs")
def hcpcs():
    """HCPCS procedure code spending with optional code/description filter."""
    from app.models import MvHcpcsSpending

    code_search = request.args.get("code", "").strip()

    query = MvHcpcsSpending.query

    # [EN] Filter by code or description — partial match on hcpcs_code or short_description
    # [RU] Фильтр по коду или описанию — частичное совпадение
    # [PT] Filtro por codigo ou descricao — correspondencia parcial
    if code_search:
        like = f"%{code_search}%"
        query = query.filter(
            db.or_(
                MvHcpcsSpending.hcpcs_code.ilike(like),
                MvHcpcsSpending.short_description.ilike(like),
            )
        )

    hcpcs_data = query.order_by(
        MvHcpcsSpending.total_paid.desc()
    ).limit(100).all()

    return render_template("hcpcs.html", hcpcs_data=hcpcs_data, code_search=code_search)
