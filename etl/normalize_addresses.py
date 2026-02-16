"""
Address normalization and parsing utilities using usaddress.

[EN] This module provides utilities for cleaning, parsing, and normalizing US street addresses.
     It uses the 'usaddress' library to decompose raw address strings into structured components
     (street number, direction, street name, suffix, unit type, unit number). It also standardizes
     abbreviations (e.g., "STREET" -> "ST", "NORTH" -> "N", "SUITE" -> "STE"), normalizes state
     names to 2-letter codes, and splits ZIP codes into ZIP5 and ZIP4 components.
     This is used by load_nppes.py to normalize provider addresses before database insertion.

[RU] Этот модуль предоставляет утилиты для очистки, разбора и нормализации почтовых адресов США.
     Он использует библиотеку 'usaddress' для разложения необработанных адресных строк на
     структурированные компоненты (номер дома, направление, название улицы, суффикс, тип помещения,
     номер помещения). Также стандартизирует сокращения (напр., "STREET" -> "ST", "NORTH" -> "N",
     "SUITE" -> "STE"), нормализует названия штатов в 2-буквенные коды и разделяет почтовые индексы
     на компоненты ZIP5 и ZIP4.
     Используется модулем load_nppes.py для нормализации адресов поставщиков перед вставкой в БД.

[PT] Este modulo fornece utilitarios para limpeza, analise e normalizacao de enderecos dos EUA.
     Ele usa a biblioteca 'usaddress' para decompor strings de endereco brutas em componentes
     estruturados (numero da rua, direcao, nome da rua, sufixo, tipo de unidade, numero da unidade).
     Tambem padroniza abreviacoes (ex.: "STREET" -> "ST", "NORTH" -> "N", "SUITE" -> "STE"),
     normaliza nomes de estados para codigos de 2 letras e divide CEPs em componentes ZIP5 e ZIP4.
     Usado por load_nppes.py para normalizar enderecos de provedores antes da insercao no banco.
"""

import logging
import re

import usaddress

log = logging.getLogger(__name__)

# [EN] Mapping of full street suffix names to their standard USPS abbreviations
# [RU] Соответствие полных названий суффиксов улиц и их стандартных сокращений USPS
# [PT] Mapeamento de nomes completos de sufixos de rua para suas abreviacoes padrao USPS
STREET_SUFFIX_MAP = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR",
    "PLACE": "PL", "TERRACE": "TER", "TRAIL": "TRL", "WAY": "WAY",
    "HIGHWAY": "HWY", "PARKWAY": "PKWY", "EXPRESSWAY": "EXPY",
    "FREEWAY": "FWY", "PIKE": "PIKE", "TURNPIKE": "TPKE",
}

# [EN] Mapping of full unit/occupancy type names to standard abbreviations
# [RU] Соответствие полных названий типов помещений и стандартных сокращений
# [PT] Mapeamento de nomes completos de tipos de unidade para abreviacoes padrao
UNIT_TYPE_MAP = {
    "SUITE": "STE", "APARTMENT": "APT", "BUILDING": "BLDG",
    "UNIT": "UNIT", "ROOM": "RM", "FLOOR": "FL", "DEPARTMENT": "DEPT",
    "NUMBER": "#", "SPACE": "SPC", "LOT": "LOT",
}

# [EN] Mapping of full directional names to abbreviated forms (N, S, E, W, NE, etc.)
# [RU] Соответствие полных названий направлений и сокращённых форм (N, S, E, W, NE и т.д.)
# [PT] Mapeamento de nomes completos de direcoes para formas abreviadas (N, S, E, W, NE, etc.)
DIRECTION_MAP = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}

# [EN] Mapping of full US state and territory names to their 2-letter postal abbreviations
# [RU] Соответствие полных названий штатов и территорий США и их 2-буквенных почтовых сокращений
# [PT] Mapeamento de nomes completos de estados e territorios dos EUA para abreviacoes postais de 2 letras
STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC", "PUERTO RICO": "PR", "GUAM": "GU",
    "VIRGIN ISLANDS": "VI", "AMERICAN SAMOA": "AS",
}


# [EN] Clean a text string: convert to uppercase, remove punctuation (periods, commas, hashes),
#      and collapse multiple spaces into one. Returns None for empty/blank input.
# [RU] Очистка текстовой строки: перевод в верхний регистр, удаление знаков препинания
#      (точки, запятые, решётки) и сжатие множественных пробелов в один. Возвращает None для пустого ввода.
# [PT] Limpa uma string de texto: converte para maiusculas, remove pontuacao (pontos, virgulas, cerquilhas)
#      e comprime espacos multiplos em um. Retorna None para entrada vazia.
# Parameters / Параметры / Parametros:
#   text (str | None): [EN] Raw text to clean | [RU] Необработанный текст для очистки | [PT] Texto bruto para limpar
# Returns / Возвращает / Retorna:
#   str | None: [EN] Cleaned text or None | [RU] Очищенный текст или None | [PT] Texto limpo ou None
def clean_text(text: str | None) -> str | None:
    """Uppercase, strip punctuation and extra whitespace."""
    if not text:
        return None
    text = text.upper().strip()
    # [EN] Remove periods, commas, and hash symbols that interfere with address parsing
    # [RU] Удаляем точки, запятые и решётки, которые мешают разбору адреса
    # [PT] Remove pontos, virgulas e cerquilhas que interferem na analise do endereco
    text = re.sub(r"[.,#]", "", text)
    # [EN] Collapse runs of whitespace into a single space
    # [RU] Сжимаем серии пробелов в один пробел
    # [PT] Comprime sequencias de espacos em um unico espaco
    text = re.sub(r"\s+", " ", text)
    return text or None


# [EN] Convert a state name or abbreviation to a 2-letter postal code.
#      If already 2 characters, returns as-is. If a full name, looks up in STATE_NAMES.
#      Falls back to first 2 characters if the name is not found in the mapping.
# [RU] Преобразует название штата или аббревиатуру в 2-буквенный почтовый код.
#      Если уже 2 символа, возвращает как есть. Если полное название, ищет в STATE_NAMES.
#      При отсутствии в справочнике берёт первые 2 символа.
# [PT] Converte um nome de estado ou abreviacao para um codigo postal de 2 letras.
#      Se ja tiver 2 caracteres, retorna como esta. Se for nome completo, busca em STATE_NAMES.
#      Recorre aos primeiros 2 caracteres se o nome nao for encontrado no mapeamento.
# Parameters / Параметры / Parametros:
#   state (str | None): [EN] State name or code | [RU] Название или код штата | [PT] Nome ou codigo do estado
# Returns / Возвращает / Retorna:
#   str | None: [EN] 2-letter state code or None | [RU] 2-буквенный код штата или None | [PT] Codigo de estado de 2 letras ou None
def normalize_state(state: str | None) -> str | None:
    """Convert state name or code to 2-letter abbreviation."""
    if not state:
        return None
    state = state.upper().strip()
    if len(state) == 2:
        return state
    return STATE_NAMES.get(state, state[:2] if len(state) > 2 else state)


# [EN] Extract ZIP5 (5-digit) and ZIP4 (4-digit extension) from various ZIP code formats.
#      Handles formats like "12345", "12345-6789", "123456789" by stripping non-digits first.
# [RU] Извлекает ZIP5 (5 цифр) и ZIP4 (4-значное расширение) из различных форматов почтового индекса.
#      Обрабатывает форматы вроде "12345", "12345-6789", "123456789", предварительно удаляя нецифровые символы.
# [PT] Extrai ZIP5 (5 digitos) e ZIP4 (extensao de 4 digitos) de varios formatos de CEP.
#      Lida com formatos como "12345", "12345-6789", "123456789", removendo nao-digitos primeiro.
# Parameters / Параметры / Parametros:
#   zip_code (str | None): [EN] Raw ZIP code string | [RU] Необработанная строка почтового индекса | [PT] String de CEP bruta
# Returns / Возвращает / Retorna:
#   tuple[str | None, str | None]: [EN] (ZIP5, ZIP4) tuple | [RU] Кортеж (ZIP5, ZIP4) | [PT] Tupla (ZIP5, ZIP4)
def normalize_zip(zip_code: str | None) -> tuple[str | None, str | None]:
    """Extract ZIP5 and ZIP4 from various formats."""
    if not zip_code:
        return None, None
    # [EN] Strip all non-digit characters (handles dashes, spaces, etc.)
    # [RU] Удаляем все нецифровые символы (обработка тире, пробелов и т.д.)
    # [PT] Remove todos os caracteres nao-numericos (lida com tracos, espacos, etc.)
    zip_code = re.sub(r"[^0-9]", "", str(zip_code))
    if len(zip_code) >= 9:
        return zip_code[:5], zip_code[5:9]
    if len(zip_code) >= 5:
        return zip_code[:5], None
    return None, None


# [EN] Standardize a street suffix (e.g., "STREET" -> "ST", "AVENUE" -> "AVE").
#      Returns the abbreviation from STREET_SUFFIX_MAP or the original if not found.
# [RU] Стандартизирует суффикс улицы (напр., "STREET" -> "ST", "AVENUE" -> "AVE").
#      Возвращает сокращение из STREET_SUFFIX_MAP или оригинал, если не найден.
# [PT] Padroniza um sufixo de rua (ex.: "STREET" -> "ST", "AVENUE" -> "AVE").
#      Retorna a abreviacao de STREET_SUFFIX_MAP ou o original se nao encontrado.
# Parameters / Параметры / Parametros:
#   suffix (str): [EN] Street suffix to abbreviate | [RU] Суффикс улицы для сокращения | [PT] Sufixo de rua para abreviar
# Returns / Возвращает / Retorna:
#   str: [EN] Abbreviated suffix | [RU] Сокращённый суффикс | [PT] Sufixo abreviado
def abbreviate_suffix(suffix: str) -> str:
    """Standardize street suffix abbreviations."""
    suffix = suffix.upper().strip().rstrip(".")
    return STREET_SUFFIX_MAP.get(suffix, suffix)


# [EN] Standardize a unit/occupancy type (e.g., "SUITE" -> "STE", "APARTMENT" -> "APT").
#      Returns the abbreviation from UNIT_TYPE_MAP or the original if not found.
# [RU] Стандартизирует тип помещения (напр., "SUITE" -> "STE", "APARTMENT" -> "APT").
#      Возвращает сокращение из UNIT_TYPE_MAP или оригинал, если не найден.
# [PT] Padroniza um tipo de unidade (ex.: "SUITE" -> "STE", "APARTMENT" -> "APT").
#      Retorna a abreviacao de UNIT_TYPE_MAP ou o original se nao encontrado.
# Parameters / Параметры / Parametros:
#   unit_type (str): [EN] Unit type to abbreviate | [RU] Тип помещения для сокращения | [PT] Tipo de unidade para abreviar
# Returns / Возвращает / Retorna:
#   str: [EN] Abbreviated unit type | [RU] Сокращённый тип помещения | [PT] Tipo de unidade abreviado
def abbreviate_unit_type(unit_type: str) -> str:
    """Standardize unit type abbreviations."""
    unit_type = unit_type.upper().strip().rstrip(".")
    return UNIT_TYPE_MAP.get(unit_type, unit_type)


# [EN] Standardize a directional abbreviation (e.g., "NORTH" -> "N", "SOUTHWEST" -> "SW").
#      Returns the abbreviation from DIRECTION_MAP or the original if not found.
# [RU] Стандартизирует сокращение направления (напр., "NORTH" -> "N", "SOUTHWEST" -> "SW").
#      Возвращает сокращение из DIRECTION_MAP или оригинал, если не найден.
# [PT] Padroniza uma abreviacao direcional (ex.: "NORTH" -> "N", "SOUTHWEST" -> "SW").
#      Retorna a abreviacao de DIRECTION_MAP ou o original se nao encontrado.
# Parameters / Параметры / Parametros:
#   direction (str): [EN] Direction to abbreviate | [RU] Направление для сокращения | [PT] Direcao para abreviar
# Returns / Возвращает / Retorna:
#   str: [EN] Abbreviated direction | [RU] Сокращённое направление | [PT] Direcao abreviada
def abbreviate_direction(direction: str) -> str:
    """Standardize directional abbreviations."""
    direction = direction.upper().strip().rstrip(".")
    return DIRECTION_MAP.get(direction, direction)


# [EN] Parse a street address line into structured components using the usaddress library.
#      Decomposes an address like "123 N MAIN ST STE 4" into:
#        street_number="123", street_pre_direction="N", street_name="MAIN",
#        street_suffix="ST", unit_type="STE", unit_number="4"
#      Handles RepeatedLabelError gracefully (returns empty result).
# [RU] Разбирает строку адреса на структурированные компоненты с помощью библиотеки usaddress.
#      Раскладывает адрес вроде "123 N MAIN ST STE 4" на:
#        street_number="123", street_pre_direction="N", street_name="MAIN",
#        street_suffix="ST", unit_type="STE", unit_number="4"
#      Корректно обрабатывает RepeatedLabelError (возвращает пустой результат).
# [PT] Analisa uma linha de endereco em componentes estruturados usando a biblioteca usaddress.
#      Decompoe um endereco como "123 N MAIN ST STE 4" em:
#        street_number="123", street_pre_direction="N", street_name="MAIN",
#        street_suffix="ST", unit_type="STE", unit_number="4"
#      Lida com RepeatedLabelError de forma elegante (retorna resultado vazio).
# Parameters / Параметры / Parametros:
#   street_line (str | None): [EN] Raw street address line | [RU] Необработанная строка адреса | [PT] Linha de endereco bruta
# Returns / Возвращает / Retorna:
#   dict: [EN] Dict with keys: street_number, street_pre_direction, street_name, street_suffix,
#              street_post_direction, unit_type, unit_number (all str | None)
#         [RU] Словарь с ключами: street_number, street_pre_direction, street_name, street_suffix,
#              street_post_direction, unit_type, unit_number (все str | None)
#         [PT] Dict com chaves: street_number, street_pre_direction, street_name, street_suffix,
#              street_post_direction, unit_type, unit_number (todos str | None)
def parse_street_address(street_line: str | None) -> dict:
    """
    Parse a street address into components using usaddress.

    Returns dict with keys: street_number, street_name, street_suffix,
    unit_type, unit_number.
    """
    result = {
        "street_number": None,
        "street_pre_direction": None,
        "street_name": None,
        "street_suffix": None,
        "street_post_direction": None,
        "unit_type": None,
        "unit_number": None,
    }

    if not street_line:
        return result

    cleaned = clean_text(street_line)
    if not cleaned:
        return result

    try:
        # [EN] Use usaddress.tag() to parse the address into labeled components
        # [RU] Используем usaddress.tag() для разбора адреса на помеченные компоненты
        # [PT] Usa usaddress.tag() para analisar o endereco em componentes rotulados
        tagged, addr_type = usaddress.tag(cleaned)
    except usaddress.RepeatedLabelError:
        # [EN] This error occurs when usaddress finds duplicate labels (e.g., two street names);
        #      we return empty result rather than crashing
        # [RU] Эта ошибка возникает, когда usaddress находит дублирующиеся метки (напр., два названия улиц);
        #      возвращаем пустой результат вместо аварийного завершения
        # [PT] Este erro ocorre quando usaddress encontra rotulos duplicados (ex.: dois nomes de rua);
        #      retornamos resultado vazio em vez de causar falha
        log.debug("usaddress repeated label for: %s", cleaned)
        return result

    result["street_number"] = tagged.get("AddressNumber")

    # [EN] Pre-directional (N, S, E, W, NE, etc.) appears before the street name
    # [RU] Пред-направление (N, S, E, W, NE и т.д.) стоит перед названием улицы
    # [PT] Pre-direcional (N, S, E, W, NE, etc.) aparece antes do nome da rua
    pre_dir = tagged.get("StreetNamePreDirectional")
    if pre_dir:
        result["street_pre_direction"] = abbreviate_direction(pre_dir)

    # [EN] Build the street name from core components (prefix type, modifier, name)
    # [RU] Формируем название улицы из основных компонентов (тип-префикс, модификатор, название)
    # [PT] Constroi o nome da rua a partir de componentes principais (tipo-prefixo, modificador, nome)
    name_parts = []
    for key in ["StreetNamePreType", "StreetNamePreModifier", "StreetName"]:
        val = tagged.get(key)
        if val:
            name_parts.append(val)
    result["street_name"] = " ".join(name_parts) if name_parts else None

    # [EN] Post-type suffix (ST, AVE, BLVD, etc.) after the street name
    # [RU] Пост-суффикс (ST, AVE, BLVD и т.д.) после названия улицы
    # [PT] Sufixo pos-tipo (ST, AVE, BLVD, etc.) apos o nome da rua
    suffix = tagged.get("StreetNamePostType")
    if suffix:
        result["street_suffix"] = abbreviate_suffix(suffix)

    # [EN] Post-directional (e.g., "123 Main St N") — direction after the street suffix
    # [RU] Пост-направление (напр., "123 Main St N") — направление после суффикса улицы
    # [PT] Pos-direcional (ex.: "123 Main St N") — direcao apos o sufixo da rua
    post_dir = tagged.get("StreetNamePostDirectional")
    if post_dir:
        result["street_post_direction"] = abbreviate_direction(post_dir)

    # [EN] Unit/occupancy type (STE, APT, BLDG, etc.) and its identifier
    # [RU] Тип помещения (STE, APT, BLDG и т.д.) и его идентификатор
    # [PT] Tipo de unidade (STE, APT, BLDG, etc.) e seu identificador
    unit_type = tagged.get("OccupancyType")
    if unit_type:
        result["unit_type"] = abbreviate_unit_type(unit_type)

    result["unit_number"] = tagged.get("OccupancyIdentifier")

    return result


# [EN] Normalize a full address record: clean text, parse street components, normalize
#      state code and ZIP code. If street line 2 contains unit info and line 1 doesn't,
#      the unit info is extracted from line 2.
#      Returns a dictionary with all cleaned/parsed fields ready for database insertion.
# [RU] Нормализация полной записи адреса: очистка текста, разбор компонентов улицы,
#      нормализация кода штата и почтового индекса. Если строка адреса 2 содержит информацию
#      о помещении, а строка 1 — нет, информация о помещении извлекается из строки 2.
#      Возвращает словарь со всеми очищенными/разобранными полями для вставки в БД.
# [PT] Normaliza um registro completo de endereco: limpa texto, analisa componentes da rua,
#      normaliza codigo do estado e CEP. Se a linha 2 do endereco contem informacoes de unidade
#      e a linha 1 nao, as informacoes de unidade sao extraidas da linha 2.
#      Retorna um dicionario com todos os campos limpos/analisados prontos para insercao no banco.
# Parameters / Параметры / Parametros:
#   street_line_1 (str | None): [EN] Primary street address | [RU] Основной адрес | [PT] Endereco principal
#   street_line_2 (str | None): [EN] Secondary address (apt/suite) | [RU] Дополнительный адрес (кв./офис) | [PT] Endereco secundario (apto/sala)
#   city (str | None):          [EN] City name | [RU] Название города | [PT] Nome da cidade
#   state (str | None):         [EN] State name or code | [RU] Название или код штата | [PT] Nome ou codigo do estado
#   zip_code (str | None):      [EN] ZIP code | [RU] Почтовый индекс | [PT] CEP
#   phone (str | None):         [EN] Phone number | [RU] Номер телефона | [PT] Numero de telefone
#   fax (str | None):           [EN] Fax number | [RU] Номер факса | [PT] Numero de fax
# Returns / Возвращает / Retorna:
#   dict: [EN] Normalized address dictionary with all fields | [RU] Словарь нормализованного адреса | [PT] Dicionario de endereco normalizado
def normalize_address(
    street_line_1: str | None,
    street_line_2: str | None,
    city: str | None,
    state: str | None,
    zip_code: str | None,
    phone: str | None = None,
    fax: str | None = None,
) -> dict:
    """
    Normalize a full address record.

    Returns a dict with all cleaned/parsed fields ready for DB insertion.
    """
    # [EN] Clean all text fields: uppercase, remove punctuation, collapse whitespace
    # [RU] Очистка всех текстовых полей: верхний регистр, удаление пунктуации, сжатие пробелов
    # [PT] Limpa todos os campos de texto: maiusculas, remove pontuacao, comprime espacos
    street_line_1 = clean_text(street_line_1)
    street_line_2 = clean_text(street_line_2)
    city = clean_text(city)
    state_code = normalize_state(state)
    zip5, zip4 = normalize_zip(zip_code)

    # [EN] Parse the primary street line into structured components
    # [RU] Разбираем основную строку адреса на структурированные компоненты
    # [PT] Analisa a linha principal do endereco em componentes estruturados
    parsed = parse_street_address(street_line_1)

    # [EN] If line 1 has no unit info but line 2 looks like a unit (e.g., "STE 100"), parse it
    # [RU] Если строка 1 не содержит информации о помещении, а строка 2 похожа на помещение (напр., "STE 100"), разбираем её
    # [PT] Se a linha 1 nao tem info de unidade mas a linha 2 parece uma unidade (ex.: "STE 100"), analisa-a
    if street_line_2 and not parsed["unit_type"]:
        line2_parsed = parse_street_address(street_line_2)
        if line2_parsed["unit_type"]:
            parsed["unit_type"] = line2_parsed["unit_type"]
            parsed["unit_number"] = line2_parsed["unit_number"]

    return {
        "street_line_1": street_line_1,
        "street_line_2": street_line_2,
        "city": city,
        "state_code": state_code,
        "zip5": zip5,
        "zip4": zip4,
        "country_code": "US",
        "phone": clean_text(phone),
        "fax": clean_text(fax),
        "street_number": parsed["street_number"],
        "street_pre_direction": parsed["street_pre_direction"],
        "street_name": parsed["street_name"],
        "street_suffix": parsed["street_suffix"],
        "street_post_direction": parsed["street_post_direction"],
        "unit_type": parsed["unit_type"],
        "unit_number": parsed["unit_number"],
    }
