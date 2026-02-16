"""
[EN] Provider search and detail routes.
     Provides a searchable, sortable, paginated list of providers ranked by spending,
     and a detail page for individual providers showing addresses, taxonomies,
     monthly spending history, and top procedure codes.

[RU] Маршруты поиска и детальной информации о поставщиках.
     Предоставляет список поставщиков с поиском, сортировкой и пагинацией по расходам,
     а также детальную страницу с адресами, таксономиями,
     историей ежемесячных расходов и основными кодами процедур.

[PT] Rotas de busca e detalhes de provedores.
     Fornece uma lista pesquisável, ordenável e paginada de provedores classificados por gastos,
     e uma página de detalhes para provedores individuais mostrando endereços, taxonomias,
     histórico mensal de gastos e principais códigos de procedimento.
"""

from flask import Blueprint, render_template, request

from app.models import (
    db, Provider, Address, ProviderTaxonomy, Spending,
    MvProviderSpendingSummary,
)

# [EN] Create the "providers" blueprint — handles provider-related HTML pages
# [RU] Создать блюпринт «providers» — обрабатывает HTML-страницы, связанные с поставщиками
# [PT] Criar o blueprint "providers" — gerencia as páginas HTML relacionadas a provedores
bp = Blueprint("providers", __name__)


# [EN] Provider list page ("/providers") — searchable, sortable, paginated rankings.
#      Supports query params: q (search text), state (filter), sort (column), order (asc/desc), page, per_page.
# [RU] Страница списка поставщиков ("/providers") — рейтинг с поиском, сортировкой и пагинацией.
#      Поддерживает параметры запроса: q (поиск), state (фильтр), sort (столбец), order (asc/desc), page, per_page.
# [PT] Página de lista de provedores ("/providers") — classificação com busca, ordenação e paginação.
#      Suporta parâmetros: q (texto de busca), state (filtro), sort (coluna), order (asc/desc), page, per_page.
@bp.route("/providers")
def provider_list():
    """Searchable/sortable provider rankings."""
    # [EN] Extract query parameters from the URL with default values
    # [RU] Извлечь параметры запроса из URL со значениями по умолчанию
    # [PT] Extrair parâmetros de consulta da URL com valores padrão
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("q", "").strip()
    state = request.args.get("state", "").strip()
    sort = request.args.get("sort", "lifetime_paid")
    order = request.args.get("order", "desc")

    query = MvProviderSpendingSummary.query

    # [EN] If search text is provided, filter by NPI, organization name, last name, or first name.
    #      Uses ILIKE for case-insensitive partial matching (SQL LIKE with % wildcards).
    # [RU] Если указан текст поиска, фильтровать по NPI, названию организации, фамилии или имени.
    #      Используется ILIKE для нечувствительного к регистру частичного совпадения (SQL LIKE с символами %).
    # [PT] Se um texto de busca for fornecido, filtrar por NPI, nome da organização, sobrenome ou nome.
    #      Usa ILIKE para correspondência parcial sem distinção de maiúsculas (SQL LIKE com curingas %).
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

    # [EN] If a state code is provided, filter results to that state only
    # [RU] Если указан код штата, фильтровать результаты только по этому штату
    # [PT] Se um código de estado for fornecido, filtrar resultados apenas para esse estado
    if state:
        query = query.filter(MvProviderSpendingSummary.state_code == state.upper())

    # [EN] Dynamic sorting: get the column attribute by name, default to lifetime_paid.
    #      Apply ascending or descending order based on the "order" parameter.
    # [RU] Динамическая сортировка: получить атрибут столбца по имени, по умолчанию lifetime_paid.
    #      Применить сортировку по возрастанию или убыванию на основе параметра «order».
    # [PT] Ordenação dinâmica: obter o atributo da coluna pelo nome, padrão lifetime_paid.
    #      Aplicar ordem crescente ou decrescente com base no parâmetro "order".
    sort_col = getattr(MvProviderSpendingSummary, sort, MvProviderSpendingSummary.lifetime_paid)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # [EN] Paginate results — error_out=False returns an empty page instead of 404 for out-of-range pages
    # [RU] Пагинация результатов — error_out=False возвращает пустую страницу вместо 404 для страниц вне диапазона
    # [PT] Paginar resultados — error_out=False retorna uma página vazia em vez de 404 para páginas fora do intervalo
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # [EN] Get all distinct state codes for the filter dropdown in the UI
    # [RU] Получить все уникальные коды штатов для выпадающего фильтра в интерфейсе
    # [PT] Obter todos os códigos de estado distintos para o filtro dropdown na interface
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


# [EN] Provider detail page ("/providers/<npi>") — shows all information for a single provider.
#      Loads the provider record, all addresses, taxonomy codes, monthly spending, and top HCPCS codes.
# [RU] Страница детальной информации о поставщике ("/providers/<npi>") — показывает всю информацию по одному поставщику.
#      Загружает запись поставщика, все адреса, коды таксономий, ежемесячные расходы и основные коды HCPCS.
# [PT] Página de detalhes do provedor ("/providers/<npi>") — mostra todas as informações de um provedor.
#      Carrega o registro do provedor, todos os endereços, códigos de taxonomia, gastos mensais e principais códigos HCPCS.
@bp.route("/providers/<npi>")
def provider_detail(npi):
    """Single provider detail view."""
    # [EN] Fetch provider by NPI primary key, return 404 if not found
    # [RU] Найти поставщика по первичному ключу NPI, вернуть 404 если не найден
    # [PT] Buscar provedor pela chave primária NPI, retornar 404 se não encontrado
    provider = Provider.query.get_or_404(npi)
    addresses = Address.query.filter_by(npi=npi).all()
    taxonomies = ProviderTaxonomy.query.filter_by(npi=npi).all()

    # [EN] Aggregate this provider's spending by month: sum total_paid, total_claims, and total_benes.
    #      GROUP BY claim_month, ordered chronologically for chart rendering.
    # [RU] Агрегировать расходы поставщика по месяцам: сумма total_paid, total_claims и total_benes.
    #      GROUP BY claim_month, упорядоченные хронологически для отображения на графике.
    # [PT] Agregar os gastos do provedor por mês: soma de total_paid, total_claims e total_benes.
    #      GROUP BY claim_month, ordenados cronologicamente para renderização de gráficos.
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

    # [EN] Get top 20 HCPCS procedure codes for this provider, ranked by total spending.
    #      GROUP BY hcpcs_code, ordered by sum(total_paid) descending.
    # [RU] Получить топ-20 кодов процедур HCPCS для этого поставщика, ранжированных по расходам.
    #      GROUP BY hcpcs_code, упорядоченных по сумме(total_paid) по убыванию.
    # [PT] Obter os 20 principais códigos HCPCS para este provedor, classificados por gasto total.
    #      GROUP BY hcpcs_code, ordenados por sum(total_paid) decrescente.
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

    # [EN] Load pre-computed summary stats from the materialized view (lifetime totals)
    # [RU] Загрузить предварительно вычисленную сводную статистику из материализованного представления (итоги за всё время)
    # [PT] Carregar estatísticas resumidas pré-calculadas da view materializada (totais acumulados)
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
