"""
Load NPPES NPI Registry data into PostgreSQL (providers, addresses, taxonomies).

[EN] This module loads the NPPES (National Plan and Provider Enumeration System) NPI Registry
     data into three PostgreSQL tables: providers, addresses, and provider_taxonomies.
     It can optionally filter to only NPIs that appear in the spending table to reduce
     data volume. Each NPPES row produces one provider record, two addresses (mailing +
     practice), and up to 15 taxonomy entries. Addresses are normalized using the
     normalize_addresses module before insertion.

[RU] Этот модуль загружает данные реестра NPI NPPES (Национальная система нумерации планов
     и поставщиков) в три таблицы PostgreSQL: providers, addresses и provider_taxonomies.
     Может опционально фильтровать только те NPI, которые присутствуют в таблице расходов,
     для уменьшения объёма данных. Каждая строка NPPES порождает одну запись поставщика,
     два адреса (почтовый + практики) и до 15 записей таксономии. Адреса нормализуются
     с помощью модуля normalize_addresses перед вставкой.

[PT] Este modulo carrega os dados do registro NPI do NPPES (Sistema Nacional de Enumeracao de
     Planos e Provedores) em tres tabelas PostgreSQL: providers, addresses e provider_taxonomies.
     Pode opcionalmente filtrar apenas os NPIs presentes na tabela de gastos para reduzir o
     volume de dados. Cada linha do NPPES gera um registro de provedor, dois enderecos
     (correspondencia + consultorio) e ate 15 entradas de taxonomia. Os enderecos sao
     normalizados usando o modulo normalize_addresses antes da insercao.
"""

import csv
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from etl.normalize_addresses import normalize_address

# [EN] Configure logging with timestamp, log level, and message format
# [RU] Настройка логирования с меткой времени, уровнем и форматом сообщения
# [PT] Configuracao de logging com timestamp, nivel e formato de mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# [EN] Paths to the raw NPPES data directory
# [RU] Пути к директории с необработанными данными NPPES
# [PT] Caminhos para o diretorio de dados brutos do NPPES
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"
NPPES_DIR = RAW_DATA_DIR / "nppes"

# [EN] Number of provider records per batch before flushing to the database
# [RU] Количество записей поставщиков в пакете перед записью в базу данных
# [PT] Numero de registros de provedores por lote antes de descarregar no banco de dados
BATCH_SIZE = 10_000


# [EN] Find the main NPPES data CSV file in the nppes/ directory.
#      Looks for files matching the pattern "npidata_pfile_*.csv" and returns the largest one.
# [RU] Поиск основного CSV-файла данных NPPES в директории nppes/.
#      Ищет файлы по шаблону "npidata_pfile_*.csv" и возвращает самый большой из них.
# [PT] Busca o arquivo CSV principal de dados NPPES no diretorio nppes/.
#      Procura arquivos correspondentes ao padrao "npidata_pfile_*.csv" e retorna o maior.
# Returns / Возвращает / Retorna:
#   Path | None: [EN] Path to the NPPES CSV or None if not found | [RU] Путь к CSV NPPES или None | [PT] Caminho do CSV NPPES ou None
def find_nppes_csv() -> Path | None:
    """Find the main NPPES data file."""
    candidates = list(NPPES_DIR.glob("npidata_pfile_*.csv"))
    if candidates:
        # [EN] Return the largest file (most likely the full dataset, not a header-only file)
        # [RU] Возвращаем самый большой файл (скорее всего полный набор данных, а не только заголовки)
        # [PT] Retorna o maior arquivo (provavelmente o conjunto de dados completo, nao apenas cabecalhos)
        return sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]
    return None


# [EN] Parse a date string in MM/DD/YYYY format (used by NPPES) into a Python date object.
# [RU] Разбирает строку даты в формате ММ/ДД/ГГГГ (используемом NPPES) в объект даты Python.
# [PT] Converte uma string de data no formato MM/DD/AAAA (usado pelo NPPES) em um objeto date do Python.
# Parameters / Параметры / Parametros:
#   val (str): [EN] Date string in MM/DD/YYYY format | [RU] Строка даты в формате ММ/ДД/ГГГГ | [PT] String de data no formato MM/DD/AAAA
# Returns / Возвращает / Retorna:
#   date | None: [EN] Parsed date or None | [RU] Разобранная дата или None | [PT] Data convertida ou None
def parse_date(val: str) -> date | None:
    """Parse MM/DD/YYYY date from NPPES."""
    if not val or val.strip() == "":
        return None
    try:
        return datetime.strptime(val.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


# [EN] Parse a Y/N string into a Python boolean (True/False/None).
# [RU] Разбирает строку Y/N в логическое значение Python (True/False/None).
# [PT] Converte uma string Y/N em booleano Python (True/False/None).
# Parameters / Параметры / Parametros:
#   val (str): [EN] "Y" or "N" string | [RU] Строка "Y" или "N" | [PT] String "Y" ou "N"
# Returns / Возвращает / Retorna:
#   bool | None: [EN] True for "Y", False for "N", None otherwise | [RU] True для "Y", False для "N", иначе None | [PT] True para "Y", False para "N", None caso contrario
def parse_bool(val: str) -> bool | None:
    """Parse Y/N boolean."""
    if not val:
        return None
    val = val.strip().upper()
    if val == "Y":
        return True
    if val == "N":
        return False
    return None


# [EN] Query the spending table to get all unique NPIs (both billing and servicing).
#      Used to filter the NPPES data so only relevant providers are loaded.
# [RU] Запрашивает таблицу расходов для получения всех уникальных NPI (как выставляющих счета, так и обслуживающих).
#      Используется для фильтрации данных NPPES, чтобы загружать только релевантных поставщиков.
# [PT] Consulta a tabela de gastos para obter todos os NPIs unicos (tanto de faturamento quanto de atendimento).
#      Usado para filtrar os dados NPPES para carregar apenas provedores relevantes.
# Parameters / Параметры / Parametros:
#   database_url (str): [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
# Returns / Возвращает / Retorna:
#   set[str]: [EN] Set of unique NPI strings | [RU] Множество уникальных строк NPI | [PT] Conjunto de strings NPI unicas
def get_relevant_npis(database_url: str) -> set[str]:
    """Get the set of NPIs from the spending table to filter NPPES."""
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    # [EN] UNION of billing and servicing NPIs to get all unique NPIs from spending data
    # [RU] UNION NPI выставляющих счета и обслуживающих для получения всех уникальных NPI из данных расходов
    # [PT] UNION dos NPIs de faturamento e atendimento para obter todos os NPIs unicos dos dados de gastos
    cur.execute("""
        SELECT DISTINCT npi FROM (
            SELECT billing_npi AS npi FROM spending
            UNION
            SELECT servicing_npi AS npi FROM spending
        ) all_npis
    """)
    npis = {row[0].strip() for row in cur.fetchall()}
    cur.close()
    conn.close()
    log.info("Found %d unique NPIs in spending data", len(npis))
    return npis


# [EN] Main function: loads NPPES data into PostgreSQL tables (providers, addresses, taxonomies).
#      Optionally filters to only NPIs present in the spending table.
#      Processes the CSV in batches for efficient memory usage and database writes.
# [RU] Основная функция: загружает данные NPPES в таблицы PostgreSQL (providers, addresses, taxonomies).
#      Опционально фильтрует только NPI, присутствующие в таблице расходов.
#      Обрабатывает CSV пакетами для эффективного использования памяти и записи в БД.
# [PT] Funcao principal: carrega dados NPPES nas tabelas PostgreSQL (providers, addresses, taxonomies).
#      Opcionalmente filtra apenas os NPIs presentes na tabela de gastos.
#      Processa o CSV em lotes para uso eficiente de memoria e gravacoes no banco.
# Parameters / Параметры / Parametros:
#   database_url (str | None):       [EN] PostgreSQL connection string | [RU] Строка подключения | [PT] String de conexao
#   filter_to_spending (bool):       [EN] If True, only load NPIs found in spending table | [RU] Если True, загружать только NPI из таблицы расходов | [PT] Se True, carrega apenas NPIs da tabela de gastos
def load_nppes(database_url: str | None = None, filter_to_spending: bool = True):
    """Load NPPES data, optionally filtered to NPIs in spending table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    nppes_csv = find_nppes_csv()
    if not nppes_csv:
        log.error("NPPES CSV not found in %s", NPPES_DIR)
        sys.exit(1)

    log.info("Loading NPPES from %s", nppes_csv)

    # [EN] Optionally get the set of NPIs from the spending table for filtering
    # [RU] Опционально получаем множество NPI из таблицы расходов для фильтрации
    # [PT] Opcionalmente obtem o conjunto de NPIs da tabela de gastos para filtragem
    relevant_npis = None
    if filter_to_spending:
        relevant_npis = get_relevant_npis(database_url)
        if not relevant_npis:
            log.warning("No NPIs found in spending table — loading all NPPES records")
            relevant_npis = None

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    # [EN] Clear existing data in reverse dependency order (taxonomies -> addresses -> providers)
    # [RU] Очистка существующих данных в обратном порядке зависимостей (таксономии -> адреса -> поставщики)
    # [PT] Limpa dados existentes na ordem inversa de dependencias (taxonomias -> enderecos -> provedores)
    cur.execute("TRUNCATE TABLE provider_taxonomies CASCADE")
    cur.execute("TRUNCATE TABLE addresses CASCADE")
    cur.execute("TRUNCATE TABLE providers CASCADE")
    conn.commit()
    log.info("Truncated providers, addresses, taxonomies tables")

    providers_loaded = 0
    addresses_loaded = 0
    taxonomies_loaded = 0
    skipped = 0

    with open(nppes_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        provider_batch = []
        address_batch = []
        taxonomy_batch = []

        for row in reader:
            # [EN] Validate NPI: must be exactly 10 digits
            # [RU] Валидация NPI: должен состоять ровно из 10 цифр
            # [PT] Validacao do NPI: deve ter exatamente 10 digitos
            npi = row.get("NPI", "").strip()
            if not npi or len(npi) != 10:
                skipped += 1
                continue

            # [EN] Skip NPIs not present in the spending data (if filtering is enabled)
            # [RU] Пропускаем NPI, отсутствующие в данных расходов (если фильтрация включена)
            # [PT] Pula NPIs ausentes nos dados de gastos (se a filtragem estiver habilitada)
            if relevant_npis and npi not in relevant_npis:
                continue

            # [EN] Entity type: 1 = Individual, 2 = Organization; skip anything else
            # [RU] Тип субъекта: 1 = Физическое лицо, 2 = Организация; пропускаем всё остальное
            # [PT] Tipo de entidade: 1 = Individual, 2 = Organizacao; pula qualquer outro
            entity_type = row.get("Entity Type Code", "").strip()
            if entity_type not in ("1", "2"):
                skipped += 1
                continue

            # [EN] Build the provider record tuple with all demographic fields
            # [RU] Формируем кортеж записи поставщика со всеми демографическими полями
            # [PT] Constroi a tupla do registro do provedor com todos os campos demograficos
            provider = (
                npi,
                int(entity_type),
                row.get("Provider Organization Name (Legal Business Name)", "").strip() or None,
                row.get("Provider Last Name (Legal Name)", "").strip() or None,
                row.get("Provider First Name", "").strip() or None,
                row.get("Provider Middle Name", "").strip() or None,
                row.get("Provider Credential Text", "").strip() or None,
                parse_bool(row.get("Is Sole Proprietor")),
                parse_bool(row.get("Is Organization Subpart")),
                row.get("Parent Organization LBN", "").strip() or None,
                row.get("Parent Organization TIN", "").strip() or None,
                row.get("Authorized Official Last Name", "").strip() or None,
                row.get("Authorized Official First Name", "").strip() or None,
                row.get("Authorized Official Telephone Number", "").strip() or None,
                parse_date(row.get("Provider Enumeration Date")),
                parse_date(row.get("Last Update Date")),
                parse_date(row.get("NPI Deactivation Date")),
                parse_date(row.get("NPI Reactivation Date")),
            )
            provider_batch.append(provider)

            # [EN] Normalize and store the mailing address (business correspondence address)
            # [RU] Нормализация и сохранение почтового адреса (адрес для деловой корреспонденции)
            # [PT] Normaliza e armazena o endereco de correspondencia (endereco comercial para correspondencia)
            mailing_addr = normalize_address(
                street_line_1=row.get("Provider First Line Business Mailing Address"),
                street_line_2=row.get("Provider Second Line Business Mailing Address"),
                city=row.get("Provider Business Mailing Address City Name"),
                state=row.get("Provider Business Mailing Address State Name"),
                zip_code=row.get("Provider Business Mailing Address Postal Code"),
                phone=row.get("Provider Business Mailing Address Telephone Number"),
                fax=row.get("Provider Business Mailing Address Fax Number"),
            )
            address_batch.append((npi, "MAILING", mailing_addr))

            # [EN] Normalize and store the practice location address (where patients are seen)
            # [RU] Нормализация и сохранение адреса практики (где принимают пациентов)
            # [PT] Normaliza e armazena o endereco do consultorio (onde os pacientes sao atendidos)
            practice_addr = normalize_address(
                street_line_1=row.get("Provider First Line Business Practice Location Address"),
                street_line_2=row.get("Provider Second Line Business Practice Location Address"),
                city=row.get("Provider Business Practice Location Address City Name"),
                state=row.get("Provider Business Practice Location Address State Name"),
                zip_code=row.get("Provider Business Practice Location Address Postal Code"),
                phone=row.get("Provider Business Practice Location Address Telephone Number"),
                fax=row.get("Provider Business Practice Location Address Fax Number"),
            )
            address_batch.append((npi, "PRACTICE", practice_addr))

            # [EN] Extract up to 15 taxonomy codes per provider (NPPES allows up to 15)
            # [RU] Извлечение до 15 кодов таксономии на поставщика (NPPES допускает до 15)
            # [PT] Extrai ate 15 codigos de taxonomia por provedor (NPPES permite ate 15)
            for i in range(1, 16):
                tax_code = row.get(f"Healthcare Provider Taxonomy Code_{i}", "").strip()
                if not tax_code:
                    continue
                license_num = row.get(f"Provider License Number_{i}", "").strip() or None
                license_state = row.get(f"Provider License Number State Code_{i}", "").strip() or None
                is_primary = row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}", "").strip().upper() == "Y"
                taxonomy_batch.append((npi, tax_code, license_num, license_state, is_primary))

            # [EN] Flush all three batches to the database when provider batch reaches BATCH_SIZE
            # [RU] Записываем все три пакета в базу данных, когда пакет поставщиков достигает BATCH_SIZE
            # [PT] Descarrega os tres lotes no banco de dados quando o lote de provedores atinge BATCH_SIZE
            if len(provider_batch) >= BATCH_SIZE:
                _flush_providers(cur, provider_batch)
                _flush_addresses(cur, address_batch)
                _flush_taxonomies(cur, taxonomy_batch)
                conn.commit()
                providers_loaded += len(provider_batch)
                addresses_loaded += len(address_batch)
                taxonomies_loaded += len(taxonomy_batch)
                log.info(
                    "Loaded %d providers, %d addresses, %d taxonomies (%d skipped)",
                    providers_loaded, addresses_loaded, taxonomies_loaded, skipped,
                )
                provider_batch = []
                address_batch = []
                taxonomy_batch = []

        # [EN] Flush the final partial batch remaining after the loop
        # [RU] Записываем последний неполный пакет, оставшийся после цикла
        # [PT] Descarrega o ultimo lote parcial restante apos o loop
        if provider_batch:
            _flush_providers(cur, provider_batch)
            _flush_addresses(cur, address_batch)
            _flush_taxonomies(cur, taxonomy_batch)
            conn.commit()
            providers_loaded += len(provider_batch)
            addresses_loaded += len(address_batch)
            taxonomies_loaded += len(taxonomy_batch)

    cur.close()
    conn.close()

    log.info("=== NPPES load complete ===")
    log.info("Providers: %d", providers_loaded)
    log.info("Addresses: %d", addresses_loaded)
    log.info("Taxonomies: %d", taxonomies_loaded)
    log.info("Skipped: %d", skipped)


# [EN] Insert a batch of provider records into the providers table.
#      Uses INSERT ... ON CONFLICT (npi) DO UPDATE to handle duplicate NPIs
#      by updating key fields (entity_type, names, last_update_date).
# [RU] Вставляет пакет записей поставщиков в таблицу providers.
#      Использует INSERT ... ON CONFLICT (npi) DO UPDATE для обработки дублирующихся NPI,
#      обновляя ключевые поля (entity_type, имена, last_update_date).
# [PT] Insere um lote de registros de provedores na tabela providers.
#      Usa INSERT ... ON CONFLICT (npi) DO UPDATE para tratar NPIs duplicados,
#      atualizando campos-chave (entity_type, nomes, last_update_date).
# Parameters / Параметры / Parametros:
#   cur:          [EN] psycopg2 cursor | [RU] Курсор psycopg2 | [PT] Cursor psycopg2
#   batch (list): [EN] List of provider tuples | [RU] Список кортежей поставщиков | [PT] Lista de tuplas de provedores
def _flush_providers(cur, batch):
    """Insert provider batch using execute_values for speed."""
    if not batch:
        return
    # Deduplicate by NPI (index 0) — keep last occurrence
    seen = {}
    for p in batch:
        seen[p[0]] = p
    deduped = list(seen.values())
    execute_values(
        cur,
        """INSERT INTO providers
           (npi, entity_type, organization_name, last_name, first_name,
            middle_name, credential, is_sole_proprietor, is_org_subpart,
            parent_org_name, parent_org_tin, authorized_official_last,
            authorized_official_first, authorized_official_phone,
            enumeration_date, last_update_date, deactivation_date,
            reactivation_date)
           VALUES %s
           ON CONFLICT (npi) DO UPDATE SET
            entity_type = EXCLUDED.entity_type,
            organization_name = EXCLUDED.organization_name,
            last_name = EXCLUDED.last_name,
            first_name = EXCLUDED.first_name,
            last_update_date = EXCLUDED.last_update_date""",
        deduped,
        page_size=1000,
    )


# [EN] Insert a batch of address records into the addresses table.
#      Each address includes both original fields (street_line_1, city, etc.) and
#      parsed/normalized components (street_number, street_name, street_suffix, etc.).
#      Uses ON CONFLICT (npi, address_purpose) DO UPDATE to overwrite existing addresses.
# [RU] Вставляет пакет записей адресов в таблицу addresses.
#      Каждый адрес содержит как исходные поля (street_line_1, city и т.д.), так и
#      разобранные/нормализованные компоненты (street_number, street_name, street_suffix и т.д.).
#      Использует ON CONFLICT (npi, address_purpose) DO UPDATE для перезаписи существующих адресов.
# [PT] Insere um lote de registros de enderecos na tabela addresses.
#      Cada endereco inclui campos originais (street_line_1, city, etc.) e
#      componentes analisados/normalizados (street_number, street_name, street_suffix, etc.).
#      Usa ON CONFLICT (npi, address_purpose) DO UPDATE para sobrescrever enderecos existentes.
# Parameters / Параметры / Parametros:
#   cur:          [EN] psycopg2 cursor | [RU] Курсор psycopg2 | [PT] Cursor psycopg2
#   batch (list): [EN] List of (npi, purpose, addr_dict) tuples | [RU] Список кортежей (npi, purpose, addr_dict) | [PT] Lista de tuplas (npi, purpose, addr_dict)
def _flush_addresses(cur, batch):
    """Insert address batch using execute_values for speed."""
    if not batch:
        return
    # Deduplicate by (npi, purpose) — keep last occurrence
    seen = {}
    for npi, purpose, addr in batch:
        seen[(npi, purpose)] = (npi, purpose, addr)
    deduped = list(seen.values())
    values = [
        (
            npi, purpose,
            addr["street_line_1"], addr["street_line_2"],
            addr["city"], addr["state_code"], addr["zip5"], addr["zip4"],
            addr["country_code"], addr["phone"], addr["fax"],
            addr["street_number"], addr["street_pre_direction"],
            addr["street_name"], addr["street_suffix"],
            addr["street_post_direction"],
            addr["unit_type"], addr["unit_number"],
        )
        for npi, purpose, addr in deduped
    ]
    execute_values(
        cur,
        """INSERT INTO addresses
           (npi, address_purpose, street_line_1, street_line_2,
            city, state_code, zip5, zip4, country_code, phone, fax,
            street_number, street_pre_direction, street_name,
            street_suffix, street_post_direction, unit_type, unit_number)
           VALUES %s
           ON CONFLICT (npi, address_purpose) DO UPDATE SET
            street_line_1 = EXCLUDED.street_line_1,
            city = EXCLUDED.city,
            state_code = EXCLUDED.state_code,
            zip5 = EXCLUDED.zip5,
            street_number = EXCLUDED.street_number,
            street_pre_direction = EXCLUDED.street_pre_direction,
            street_name = EXCLUDED.street_name,
            street_suffix = EXCLUDED.street_suffix,
            street_post_direction = EXCLUDED.street_post_direction,
            unit_type = EXCLUDED.unit_type,
            unit_number = EXCLUDED.unit_number""",
        values,
        page_size=1000,
    )


# [EN] Insert a batch of taxonomy records into the provider_taxonomies table.
#      Each taxonomy links an NPI to a healthcare taxonomy code with optional license info.
#      Uses ON CONFLICT (npi, taxonomy_code) DO UPDATE to refresh the is_primary flag.
# [RU] Вставляет пакет записей таксономии в таблицу provider_taxonomies.
#      Каждая таксономия связывает NPI с кодом таксономии здравоохранения с необязательной информацией о лицензии.
#      Использует ON CONFLICT (npi, taxonomy_code) DO UPDATE для обновления флага is_primary.
# [PT] Insere um lote de registros de taxonomia na tabela provider_taxonomies.
#      Cada taxonomia vincula um NPI a um codigo de taxonomia de saude com informacoes opcionais de licenca.
#      Usa ON CONFLICT (npi, taxonomy_code) DO UPDATE para atualizar o flag is_primary.
# Parameters / Параметры / Parametros:
#   cur:          [EN] psycopg2 cursor | [RU] Курсор psycopg2 | [PT] Cursor psycopg2
#   batch (list): [EN] List of (npi, tax_code, license_num, license_state, is_primary) tuples
#                 [RU] Список кортежей (npi, tax_code, license_num, license_state, is_primary)
#                 [PT] Lista de tuplas (npi, tax_code, license_num, license_state, is_primary)
def _flush_taxonomies(cur, batch):
    """Insert taxonomy batch using execute_values for speed."""
    if not batch:
        return
    # Deduplicate by (npi, taxonomy_code) — keep last occurrence
    seen = {}
    for t in batch:
        seen[(t[0], t[1])] = t
    deduped = list(seen.values())
    execute_values(
        cur,
        """INSERT INTO provider_taxonomies
           (npi, taxonomy_code, license_number, license_state, is_primary)
           VALUES %s
           ON CONFLICT (npi, taxonomy_code) DO UPDATE SET
            is_primary = EXCLUDED.is_primary""",
        deduped,
        page_size=1000,
    )


# [EN] Entry point: runs the NPPES data load process
# [RU] Точка входа: запускает процесс загрузки данных NPPES
# [PT] Ponto de entrada: executa o processo de carga dos dados NPPES
def main():
    load_nppes()


if __name__ == "__main__":
    main()
