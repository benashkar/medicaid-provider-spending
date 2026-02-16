"""
Load HHS Medicaid Provider Spending CSV into PostgreSQL.

Usage:
    python -m etl.load_spending                     # Full load (truncates table first)
    python -m etl.load_spending --resume            # Resume: skip existing rows via ON CONFLICT
    python -m etl.load_spending --resume --refresh-views  # Resume + auto-refresh materialized views

[EN] This module reads the HHS Medicaid Provider Spending CSV file and bulk-loads it into
     the PostgreSQL 'spending' table. It parses dates, integers, and decimal values from
     the raw CSV, validates required fields, and uses PostgreSQL COPY for fast insertion.
     If a COPY batch fails, it falls back to row-by-row INSERT with conflict handling.
     The --refresh-views flag triggers a refresh of all materialized views after loading.

[RU] Этот модуль читает CSV-файл расходов поставщиков HHS Medicaid и массово загружает его
     в таблицу 'spending' PostgreSQL. Он разбирает даты, целые числа и десятичные значения
     из необработанного CSV, проверяет обязательные поля и использует COPY PostgreSQL для
     быстрой вставки. При ошибке пакетной вставки переключается на построчный INSERT
     с обработкой конфликтов. Флаг --refresh-views запускает обновление всех представлений.

[PT] Este modulo le o arquivo CSV de gastos de provedores HHS Medicaid e faz carga massiva
     na tabela 'spending' do PostgreSQL. Ele analisa datas, inteiros e valores decimais
     do CSV bruto, valida campos obrigatorios e usa COPY do PostgreSQL para insercao rapida.
     Se um lote COPY falhar, recorre a INSERT linha por linha com tratamento de conflitos.
     O flag --refresh-views aciona a atualizacao de todas as views materializadas.
"""

import csv
import io
import logging
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2 import sql

# [EN] Configure logging with timestamp, log level, and message format
# [RU] Настройка логирования с меткой времени, уровнем и форматом сообщения
# [PT] Configuracao de logging com timestamp, nivel e formato de mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# [EN] Path to the raw spending CSV file
# [RU] Путь к необработанному CSV-файлу расходов
# [PT] Caminho para o arquivo CSV bruto de gastos
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"
CSV_FILE = RAW_DATA_DIR / "medicaid-provider-spending.csv"

# [EN] Mapping from CSV column headers to database column names
# [RU] Соответствие заголовков столбцов CSV и имён столбцов в базе данных
# [PT] Mapeamento dos cabecalhos de colunas do CSV para os nomes de colunas no banco de dados
COLUMN_MAP = {
    "BILLING_PROVIDER_NPI_NUM": "billing_npi",
    "SERVICING_PROVIDER_NPI_NUM": "servicing_npi",
    "HCPCS_CODE": "hcpcs_code",
    "CLAIM_FROM_MONTH": "claim_month",
    "TOTAL_UNIQUE_BENEFICIARIES": "total_unique_benes",
    "TOTAL_CLAIMS": "total_claims",
    "TOTAL_PAID": "total_paid",
}

# [EN] Ordered list of database columns for COPY and INSERT operations
# [RU] Упорядоченный список столбцов БД для операций COPY и INSERT
# [PT] Lista ordenada de colunas do banco para operacoes COPY e INSERT
DB_COLUMNS = [
    "billing_npi", "servicing_npi", "hcpcs_code", "claim_month",
    "total_unique_benes", "total_claims", "total_paid",
]

# [EN] Number of rows per batch for COPY insertion (50,000 rows at a time)
# [RU] Количество строк в одном пакете для вставки COPY (50 000 строк за раз)
# [PT] Numero de linhas por lote para insercao COPY (50.000 linhas por vez)
BATCH_SIZE = 50_000


# [EN] Parse a YYYY-MM string into a Python date object (first day of month).
#      Returns None if the input is empty or has an invalid format.
# [RU] Разбирает строку YYYY-MM в объект даты Python (первый день месяца).
#      Возвращает None, если вход пуст или имеет неверный формат.
# [PT] Converte uma string YYYY-MM em um objeto date do Python (primeiro dia do mes).
#      Retorna None se a entrada estiver vazia ou tiver formato invalido.
# Parameters / Параметры / Parametros:
#   val (str): [EN] Date string in YYYY-MM format | [RU] Строка даты в формате ГГГГ-ММ | [PT] String de data no formato AAAA-MM
# Returns / Возвращает / Retorna:
#   date | None: [EN] First day of the month or None | [RU] Первый день месяца или None | [PT] Primeiro dia do mes ou None
def parse_claim_month(val: str) -> date | None:
    """Parse YYYY-MM into first-of-month date."""
    if not val:
        return None
    try:
        # [EN] Split "YYYY-MM" and construct a date with day=1
        # [RU] Разделяем "ГГГГ-ММ" и создаём дату с днём=1
        # [PT] Divide "AAAA-MM" e constroi uma data com dia=1
        parts = val.strip().split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None


# [EN] Parse a string into an integer. Returns None for empty or invalid input.
# [RU] Разбирает строку в целое число. Возвращает None для пустого или некорректного ввода.
# [PT] Converte uma string em inteiro. Retorna None para entrada vazia ou invalida.
# Parameters / Параметры / Parametros:
#   val (str): [EN] String to parse | [RU] Строка для разбора | [PT] String para converter
# Returns / Возвращает / Retorna:
#   int | None: [EN] Parsed integer or None | [RU] Разобранное целое число или None | [PT] Inteiro convertido ou None
def parse_int(val: str) -> int | None:
    """Parse integer, returning None for empty/invalid."""
    if not val or val.strip() == "":
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


# [EN] Parse a decimal/currency string into a float. Strips commas before parsing.
#      Returns None for empty or invalid input.
# [RU] Разбирает строку с десятичным/денежным значением в float. Удаляет запятые перед разбором.
#      Возвращает None для пустого или некорректного ввода.
# [PT] Converte uma string decimal/monetaria em float. Remove virgulas antes da conversao.
#      Retorna None para entrada vazia ou invalida.
# Parameters / Параметры / Parametros:
#   val (str): [EN] Decimal string (may contain commas) | [RU] Десятичная строка (может содержать запятые) | [PT] String decimal (pode conter virgulas)
# Returns / Возвращает / Retorna:
#   float | None: [EN] Parsed float or None | [RU] Разобранное число с плавающей точкой или None | [PT] Float convertido ou None
def parse_decimal(val: str) -> float | None:
    """Parse decimal/currency value."""
    if not val or val.strip() == "":
        return None
    try:
        # [EN] Remove commas used as thousands separators (e.g., "1,234.56" -> "1234.56")
        # [RU] Удаляем запятые-разделители тысяч (напр., "1,234.56" -> "1234.56")
        # [PT] Remove virgulas usadas como separadores de milhar (ex.: "1,234.56" -> "1234.56")
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


# [EN] Transform a raw CSV row dictionary into a tuple ready for database insertion.
#      Extracts and parses all required fields; returns None if any required field is missing.
#      NPI values are truncated to 10 characters (standard NPI length).
# [RU] Преобразует словарь необработанной строки CSV в кортеж для вставки в базу данных.
#      Извлекает и разбирает все обязательные поля; возвращает None при отсутствии любого обязательного поля.
#      Значения NPI обрезаются до 10 символов (стандартная длина NPI).
# [PT] Transforma um dicionario de linha CSV bruta em uma tupla pronta para insercao no banco.
#      Extrai e analisa todos os campos obrigatorios; retorna None se algum campo obrigatorio estiver ausente.
#      Valores NPI sao truncados para 10 caracteres (comprimento padrao do NPI).
# Parameters / Параметры / Parametros:
#   row (dict): [EN] CSV row as dictionary | [RU] Строка CSV в виде словаря | [PT] Linha do CSV como dicionario
# Returns / Возвращает / Retorna:
#   tuple | None: [EN] (billing_npi, servicing_npi, hcpcs_code, claim_month, benes, claims, paid) or None
#                 [RU] (billing_npi, servicing_npi, hcpcs_code, claim_month, benes, claims, paid) или None
#                 [PT] (billing_npi, servicing_npi, hcpcs_code, claim_month, benes, claims, paid) ou None
def transform_row(row: dict) -> tuple | None:
    """Transform a CSV row dict into a tuple for DB insertion."""
    billing_npi = row.get("BILLING_PROVIDER_NPI_NUM", "").strip()
    servicing_npi = row.get("SERVICING_PROVIDER_NPI_NUM", "").strip()
    hcpcs_code = row.get("HCPCS_CODE", "").strip()
    claim_month = parse_claim_month(row.get("CLAIM_FROM_MONTH", ""))

    # [EN] billing_npi and hcpcs_code are truly required; skip only if those are missing
    # [RU] billing_npi и hcpcs_code действительно обязательны; пропускаем только при их отсутствии
    # [PT] billing_npi e hcpcs_code sao realmente obrigatorios; pula apenas se estiverem ausentes
    if not billing_npi or not hcpcs_code or not claim_month:
        return None

    # [EN] When servicing_npi is empty, store as NULL to preserve original data fidelity
    #      This means the billing provider is also the servicing provider
    # [RU] Когда servicing_npi пуст, сохраняем как NULL для точности исходных данных
    #      Это означает, что биллинг-провайдер является и обслуживающим провайдером
    # [PT] Quando servicing_npi esta vazio, armazena como NULL para preservar a fidelidade dos dados
    #      Isso significa que o provedor de faturamento tambem e o provedor de servico

    return (
        billing_npi[:10],
        servicing_npi[:10] if servicing_npi else None,
        hcpcs_code,
        claim_month,
        parse_int(row.get("TOTAL_UNIQUE_BENEFICIARIES", "")),
        parse_int(row.get("TOTAL_CLAIMS", "")),
        parse_decimal(row.get("TOTAL_PAID", "")),
    )


# [EN] Use PostgreSQL COPY for fast bulk insertion of a batch of rows.
#      Builds a tab-separated in-memory buffer and streams it via copy_from.
#      None values are represented as \N (PostgreSQL NULL convention for COPY).
# [RU] Использует COPY PostgreSQL для быстрой массовой вставки пакета строк.
#      Формирует разделённый табуляцией буфер в памяти и передаёт его через copy_from.
#      Значения None представлены как \N (соглашение PostgreSQL для NULL в COPY).
# [PT] Usa COPY do PostgreSQL para insercao massiva rapida de um lote de linhas.
#      Constroi um buffer separado por tabulacao na memoria e o transmite via copy_from.
#      Valores None sao representados como \N (convencao de NULL do PostgreSQL para COPY).
# Parameters / Параметры / Parametros:
#   cur:             [EN] psycopg2 cursor | [RU] Курсор psycopg2 | [PT] Cursor psycopg2
#   batch (list):    [EN] List of row tuples | [RU] Список кортежей строк | [PT] Lista de tuplas de linhas
def copy_batch(cur, batch: list[tuple], use_staging: bool = False):
    """Use COPY for fast bulk insertion. With use_staging=True, uses a temp table to skip duplicates."""
    buf = io.StringIO()
    for row in batch:
        line = "\t".join(
            "\\N" if v is None else str(v) for v in row
        )
        buf.write(line + "\n")
    buf.seek(0)

    if use_staging:
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS spending_stage (
                billing_npi CHAR(10),
                servicing_npi CHAR(10),
                hcpcs_code VARCHAR(10),
                claim_month DATE,
                total_unique_benes INTEGER,
                total_claims INTEGER,
                total_paid NUMERIC(14,2)
            )
        """)
        cur.execute("TRUNCATE spending_stage")
        cur.copy_from(buf, "spending_stage", columns=DB_COLUMNS, null="\\N")
        cur.execute("""
            INSERT INTO spending (billing_npi, servicing_npi, hcpcs_code, claim_month,
                                  total_unique_benes, total_claims, total_paid)
            SELECT billing_npi, servicing_npi, hcpcs_code, claim_month,
                   total_unique_benes, total_claims, total_paid
            FROM spending_stage
            ON CONFLICT DO NOTHING
        """)
    else:
        cur.copy_from(buf, "spending", columns=DB_COLUMNS, null="\\N")


# [EN] Main loading function: streams the spending CSV into PostgreSQL using COPY.
#      1) Truncates the spending table for a clean reload
#      2) Reads the CSV row by row, transforms each row, and batches them
#      3) Each batch of 50,000 rows is inserted via COPY
#      4) If COPY fails, falls back to row-by-row INSERT with ON CONFLICT DO NOTHING
# [RU] Основная функция загрузки: потоково загружает CSV расходов в PostgreSQL через COPY.
#      1) Очищает таблицу spending для чистой перезагрузки
#      2) Читает CSV построчно, преобразует каждую строку и группирует их в пакеты
#      3) Каждый пакет из 50 000 строк вставляется через COPY
#      4) При ошибке COPY переключается на построчный INSERT с ON CONFLICT DO NOTHING
# [PT] Funcao principal de carga: transmite o CSV de gastos para PostgreSQL usando COPY.
#      1) Limpa a tabela spending para uma recarga completa
#      2) Le o CSV linha por linha, transforma cada linha e agrupa em lotes
#      3) Cada lote de 50.000 linhas e inserido via COPY
#      4) Se COPY falhar, recorre a INSERT linha por linha com ON CONFLICT DO NOTHING
# Parameters / Параметры / Parametros:
#   csv_path (Path | None):      [EN] Path to CSV file (default: CSV_FILE) | [RU] Путь к CSV (по умолч.: CSV_FILE) | [PT] Caminho do CSV (padrao: CSV_FILE)
#   database_url (str | None):   [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_spending(csv_path: Path | None = None, database_url: str | None = None, resume: bool = False):
    """Stream spending CSV into PostgreSQL using COPY."""
    csv_path = csv_path or CSV_FILE
    database_url = database_url or os.environ["DATABASE_URL"]

    if not csv_path.exists():
        log.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    log.info("Loading spending data from %s", csv_path)

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    if resume:
        cur.execute("SELECT COUNT(*) FROM spending")
        existing = cur.fetchone()[0]
        log.info("Resume mode: %d rows already in DB, using staging table for duplicates", existing)
    else:
        cur.execute("TRUNCATE TABLE spending RESTART IDENTITY CASCADE")
        log.info("Truncated spending table")

    total_rows = 0
    skipped = 0
    batch = []

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transformed = transform_row(row)
            if transformed is None:
                skipped += 1
                continue

            batch.append(transformed)
            if len(batch) >= BATCH_SIZE:
                try:
                    copy_batch(cur, batch, use_staging=resume)
                    conn.commit()
                    total_rows += len(batch)
                    log.info("Loaded %d rows (%d skipped)", total_rows, skipped)
                except Exception as e:
                    conn.rollback()
                    log.error("Batch insert failed at row %d: %s", total_rows, e)
                    skipped += len(batch)
                batch = []

    # [EN] Flush the final partial batch (less than BATCH_SIZE rows)
    # [RU] Записываем последний неполный пакет (менее BATCH_SIZE строк)
    # [PT] Descarrega o ultimo lote parcial (menos de BATCH_SIZE linhas)
    if batch:
        try:
            copy_batch(cur, batch, use_staging=resume)
            conn.commit()
            total_rows += len(batch)
        except Exception as e:
            conn.rollback()
            log.error("Final batch failed: %s", e)
            skipped += len(batch)

    cur.close()
    conn.close()

    log.info("=== Spending load complete ===")
    log.info("Total rows loaded: %d", total_rows)
    log.info("Rows skipped: %d", skipped)

    return total_rows


def refresh_materialized_views(database_url: str | None = None):
    """Refresh all materialized views after a data load.

    Delegates to etl.refresh_views which handles the ordered refresh
    of all 16 materialized views and reports row counts.
    """
    from etl.refresh_views import refresh_views
    database_url = database_url or os.environ["DATABASE_URL"]
    log.info("=== Auto-refreshing materialized views after load ===")
    refresh_views(database_url=database_url)


# [EN] Entry point: runs the spending data load process
# [RU] Точка входа: запускает процесс загрузки данных о расходах
# [PT] Ponto de entrada: executa o processo de carga dos dados de gastos
def main():
    resume = "--resume" in sys.argv
    do_refresh = "--refresh-views" in sys.argv
    total = load_spending(resume=resume)

    if do_refresh and total is not None:
        refresh_materialized_views()


if __name__ == "__main__":
    main()
