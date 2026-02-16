"""
[EN] JSON API endpoints for spending data (used by front-end charts).
     Returns data in JSON format for AJAX/fetch calls from the browser.
     Includes endpoints for monthly spending time series, provider search,
     and per-provider spending breakdowns.

[RU] JSON API-эндпоинты для данных о расходах (используются графиками на фронтенде).
     Возвращает данные в формате JSON для AJAX/fetch-запросов из браузера.
     Включает эндпоинты для временных рядов ежемесячных расходов, поиска поставщиков
     и детализации расходов по каждому поставщику.

[PT] Endpoints de API JSON para dados de gastos (usados por gráficos no front-end).
     Retorna dados em formato JSON para chamadas AJAX/fetch do navegador.
     Inclui endpoints para séries temporais de gastos mensais, busca de provedores
     e detalhamento de gastos por provedor.
"""

from flask import Blueprint, jsonify, request

from app.models import db, MvMonthlySpending, MvProviderSpendingSummary, Spending

# [EN] Create the "spending" blueprint with URL prefix "/api" — all routes start with /api/...
# [RU] Создать блюпринт «spending» с префиксом URL "/api" — все маршруты начинаются с /api/...
# [PT] Criar o blueprint "spending" com prefixo de URL "/api" — todas as rotas começam com /api/...
bp = Blueprint("spending", __name__, url_prefix="/api")


# [EN] Monthly spending time series ("/api/spending/monthly") — returns all months with totals.
#      Used by JavaScript charts (e.g., Chart.js or Plotly) to render spending trends.
# [RU] Временной ряд ежемесячных расходов ("/api/spending/monthly") — возвращает все месяцы с итогами.
#      Используется JavaScript-графиками (например, Chart.js или Plotly) для отображения трендов.
# [PT] Série temporal de gastos mensais ("/api/spending/monthly") — retorna todos os meses com totais.
#      Usado por gráficos JavaScript (ex.: Chart.js ou Plotly) para renderizar tendências de gastos.
@bp.route("/spending/monthly")
def monthly_spending():
    """Monthly spending time series for charts."""
    data = MvMonthlySpending.query.order_by(MvMonthlySpending.claim_month).all()

    # [EN] Convert each row to a dictionary, casting Decimal/date to float/string for JSON serialization
    # [RU] Преобразовать каждую строку в словарь, приводя Decimal/date к float/string для JSON-сериализации
    # [PT] Converter cada linha em dicionário, convertendo Decimal/date para float/string para serialização JSON
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


# [EN] Provider search API ("/api/providers/search") — returns JSON results for autocomplete/search.
#      Supports query params: q (search text), state (filter), limit (max results, default 20).
# [RU] API поиска поставщиков ("/api/providers/search") — возвращает JSON-результаты для автодополнения/поиска.
#      Поддерживает параметры: q (текст поиска), state (фильтр), limit (макс. результатов, по умолчанию 20).
# [PT] API de busca de provedores ("/api/providers/search") — retorna resultados JSON para autocomplete/busca.
#      Suporta parâmetros: q (texto de busca), state (filtro), limit (máx. resultados, padrão 20).
@bp.route("/providers/search")
def provider_search():
    """Provider search by name/NPI/state."""
    q = request.args.get("q", "").strip()
    state = request.args.get("state", "").strip()
    limit = request.args.get("limit", 20, type=int)

    query = MvProviderSpendingSummary.query

    # [EN] Filter by NPI, organization name, or last name using case-insensitive LIKE
    # [RU] Фильтровать по NPI, названию организации или фамилии с помощью нечувствительного к регистру LIKE
    # [PT] Filtrar por NPI, nome da organização ou sobrenome usando LIKE sem distinção de maiúsculas
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

    # [EN] Order by lifetime_paid descending so the highest spenders appear first
    # [RU] Сортировать по lifetime_paid по убыванию, чтобы поставщики с наибольшими расходами были первыми
    # [PT] Ordenar por lifetime_paid decrescente para que os maiores gastadores apareçam primeiro
    results = query.order_by(
        MvProviderSpendingSummary.lifetime_paid.desc()
    ).limit(limit).all()

    # [EN] Build JSON response — strip whitespace from NPI, use display_name property for the name
    # [RU] Сформировать JSON-ответ — удалить пробелы из NPI, использовать свойство display_name для имени
    # [PT] Construir resposta JSON — remover espaços do NPI, usar a propriedade display_name para o nome
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


# [EN] Per-provider spending time series ("/api/providers/<npi>/spending") — monthly breakdown for one provider.
#      Aggregates the raw spending table by month for a given billing NPI.
# [RU] Временной ряд расходов по поставщику ("/api/providers/<npi>/spending") — помесячная разбивка для одного поставщика.
#      Агрегирует таблицу расходов по месяцам для заданного NPI.
# [PT] Série temporal de gastos por provedor ("/api/providers/<npi>/spending") — detalhamento mensal para um provedor.
#      Agrega a tabela de gastos brutos por mês para um dado NPI de faturamento.
@bp.route("/providers/<npi>/spending")
def provider_spending(npi):
    """Per-provider spending time series."""
    # [EN] Group spending records by month for this NPI, summing paid/claims/beneficiaries
    # [RU] Группировать записи расходов по месяцам для этого NPI, суммируя выплаты/заявки/получателей
    # [PT] Agrupar registros de gastos por mês para este NPI, somando pagamentos/sinistros/beneficiários
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
