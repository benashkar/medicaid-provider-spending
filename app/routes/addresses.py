"""
[EN] Address analysis routes.
     Provides a page for analyzing provider addresses: identifies shared practice
     addresses (multiple providers at the same location) and reports address
     normalization quality (how many addresses have been successfully parsed).

[RU] Маршруты анализа адресов.
     Предоставляет страницу для анализа адресов поставщиков: определяет общие адреса
     практики (несколько поставщиков по одному адресу) и отображает качество
     нормализации адресов (сколько адресов было успешно разобрано).

[PT] Rotas de análise de endereços.
     Fornece uma página para analisar endereços de provedores: identifica endereços
     de consultório compartilhados (múltiplos provedores no mesmo local) e reporta
     a qualidade de normalização de endereços (quantos endereços foram analisados com sucesso).
"""

from flask import Blueprint, render_template

from app.models import db, Address

# [EN] Create the "addresses" blueprint — handles address analysis pages
# [RU] Создать блюпринт «addresses» — обрабатывает страницы анализа адресов
# [PT] Criar o blueprint "addresses" — gerencia as páginas de análise de endereços
bp = Blueprint("addresses", __name__)


# [EN] Address analysis page ("/addresses") — shows shared addresses and normalization stats.
#      Shared addresses can indicate medical groups, clinics, or billing patterns worth investigating.
# [RU] Страница анализа адресов ("/addresses") — показывает общие адреса и статистику нормализации.
#      Общие адреса могут указывать на медицинские группы, клиники или паттерны биллинга, заслуживающие исследования.
# [PT] Página de análise de endereços ("/addresses") — mostra endereços compartilhados e estatísticas de normalização.
#      Endereços compartilhados podem indicar grupos médicos, clínicas ou padrões de faturamento dignos de investigação.
@bp.route("/addresses")
def address_analysis():
    """Address analysis: shared addresses, normalization quality."""
    # [EN] Find practice addresses shared by more than 3 providers.
    #      Groups by street, city, state, zip and counts how many provider NPIs share each address.
    #      array_agg(npi) collects all NPI numbers at that address into a PostgreSQL array.
    # [RU] Найти адреса практики, общие для более чем 3 поставщиков.
    #      Группирует по улице, городу, штату, индексу и подсчитывает, сколько NPI поставщиков делят каждый адрес.
    #      array_agg(npi) собирает все номера NPI по данному адресу в массив PostgreSQL.
    # [PT] Encontrar endereços de consultório compartilhados por mais de 3 provedores.
    #      Agrupa por rua, cidade, estado, CEP e conta quantos NPIs de provedores compartilham cada endereço.
    #      array_agg(npi) coleta todos os números NPI nesse endereço em um array PostgreSQL.
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
        # [EN] Only include addresses shared by more than 3 providers
        # [RU] Включить только адреса, общие для более чем 3 поставщиков
        # [PT] Incluir apenas endereços compartilhados por mais de 3 provedores
        db.func.count(Address.npi) > 3
    ).order_by(
        # [EN] Most shared addresses first (descending by provider count)
        # [RU] Сначала наиболее разделяемые адреса (по убыванию количества поставщиков)
        # [PT] Endereços mais compartilhados primeiro (decrescente por contagem de provedores)
        db.func.count(Address.npi).desc()
    ).limit(100).all()

    # [EN] Calculate address normalization quality: what percentage of addresses have been
    #      successfully parsed into components (street_number is not null means it was parsed)
    # [RU] Рассчитать качество нормализации адресов: какой процент адресов был
    #      успешно разобран на компоненты (street_number не null означает, что адрес был разобран)
    # [PT] Calcular a qualidade da normalização de endereços: qual porcentagem de endereços foi
    #      analisada com sucesso em componentes (street_number não nulo significa que foi analisado)
    total_addresses = db.session.query(db.func.count(Address.address_id)).scalar() or 0
    parsed_count = db.session.query(
        db.func.count(Address.address_id)
    ).filter(Address.street_number.isnot(None)).scalar() or 0

    # [EN] Compute parse rate as a percentage, handle division by zero
    # [RU] Вычислить процент разбора, обработать деление на ноль
    # [PT] Calcular a taxa de análise como porcentagem, tratar divisão por zero
    parse_rate = round(parsed_count / total_addresses * 100, 1) if total_addresses else 0

    return render_template(
        "addresses.html",
        shared_addresses=shared_addresses,
        total_addresses=total_addresses,
        parsed_count=parsed_count,
        parse_rate=parse_rate,
    )
