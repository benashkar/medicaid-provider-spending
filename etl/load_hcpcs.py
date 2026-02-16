"""
Load HCPCS code reference data into PostgreSQL.

[EN] This module loads HCPCS (Healthcare Common Procedure Coding System) reference data
     into the hcpcs_codes table. It supports two strategies:
     1) If a HCPCS reference CSV file exists in raw_data/, it loads codes with their
        short/long descriptions and categories from that file.
     2) If no reference file is found, it falls back to extracting distinct HCPCS codes
        from the already-loaded spending table (codes only, without descriptions).
     This ensures the hcpcs_codes table is always populated for foreign key integrity.

[RU] Этот модуль загружает справочные данные HCPCS (Общая система кодирования процедур
     здравоохранения) в таблицу hcpcs_codes. Поддерживает две стратегии:
     1) Если CSV-файл справочника HCPCS существует в raw_data/, загружает коды с их
        краткими/полными описаниями и категориями из этого файла.
     2) Если справочный файл не найден, извлекает уникальные коды HCPCS
        из уже загруженной таблицы расходов (только коды, без описаний).
     Это гарантирует, что таблица hcpcs_codes всегда заполнена для целостности внешних ключей.

[PT] Este modulo carrega dados de referencia HCPCS (Sistema Comum de Codificacao de
     Procedimentos de Saude) na tabela hcpcs_codes. Suporta duas estrategias:
     1) Se um arquivo CSV de referencia HCPCS existir em raw_data/, carrega os codigos com
        suas descricoes curtas/longas e categorias desse arquivo.
     2) Se nenhum arquivo de referencia for encontrado, recorre a extracao de codigos HCPCS
        distintos da tabela de gastos ja carregada (apenas codigos, sem descricoes).
     Isso garante que a tabela hcpcs_codes esteja sempre preenchida para integridade referencial.
"""

import csv
import logging
import os
import sys
from pathlib import Path

import psycopg2

# [EN] Configure logging with timestamp, log level, and message format
# [RU] Настройка логирования с меткой времени, уровнем и форматом сообщения
# [PT] Configuracao de logging com timestamp, nivel e formato de mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# [EN] Base directory for raw data files
# [RU] Базовая директория для файлов необработанных данных
# [PT] Diretorio base para arquivos de dados brutos
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"


# [EN] Search for an HCPCS reference file in raw_data/ directory.
#      Looks for any file containing "hcpcs" (case-insensitive) with a CSV/TSV/TXT extension.
# [RU] Поиск справочного файла HCPCS в директории raw_data/.
#      Ищет любой файл, содержащий "hcpcs" (без учёта регистра) с расширением CSV/TSV/TXT.
# [PT] Busca um arquivo de referencia HCPCS no diretorio raw_data/.
#      Procura qualquer arquivo contendo "hcpcs" (sem diferenciar maiusculas) com extensao CSV/TSV/TXT.
# Returns / Возвращает / Retorna:
#   Path | None: [EN] Path to HCPCS file or None | [RU] Путь к файлу HCPCS или None | [PT] Caminho do arquivo HCPCS ou None
def find_hcpcs_file() -> Path | None:
    """Find HCPCS reference file in raw_data."""
    # [EN] Search both lowercase and uppercase patterns to handle different file naming
    # [RU] Поиск как строчных, так и заглавных шаблонов для обработки разных именований файлов
    # [PT] Busca padroes em minusculas e maiusculas para lidar com diferentes nomenclaturas de arquivo
    candidates = list(RAW_DATA_DIR.glob("*hcpcs*")) + list(RAW_DATA_DIR.glob("*HCPCS*"))
    for c in candidates:
        if c.suffix.lower() in (".csv", ".tsv", ".txt"):
            return c
    return None


# [EN] Fallback strategy: extract distinct HCPCS codes from the spending table.
#      Used when no HCPCS reference file is available. Inserts codes without descriptions.
#      Uses ON CONFLICT DO NOTHING to avoid duplicates.
# [RU] Запасная стратегия: извлечение уникальных кодов HCPCS из таблицы расходов.
#      Используется, когда справочный файл HCPCS недоступен. Вставляет коды без описаний.
#      Использует ON CONFLICT DO NOTHING для избежания дубликатов.
# [PT] Estrategia de fallback: extrai codigos HCPCS distintos da tabela de gastos.
#      Usado quando nenhum arquivo de referencia HCPCS esta disponivel. Insere codigos sem descricoes.
#      Usa ON CONFLICT DO NOTHING para evitar duplicatas.
# Parameters / Параметры / Parametros:
#   database_url (str): [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_hcpcs_from_spending(database_url: str):
    """
    Extract distinct HCPCS codes from spending table as a fallback
    when no HCPCS reference file is available.
    """
    log.info("No HCPCS file found — extracting codes from spending table")
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # [EN] Insert distinct HCPCS codes from spending; skip any that already exist
    # [RU] Вставляем уникальные коды HCPCS из расходов; пропускаем уже существующие
    # [PT] Insere codigos HCPCS distintos dos gastos; pula os que ja existem
    cur.execute("""
        INSERT INTO hcpcs_codes (hcpcs_code)
        SELECT DISTINCT hcpcs_code FROM spending
        WHERE hcpcs_code IS NOT NULL
        ON CONFLICT (hcpcs_code) DO NOTHING
    """)
    inserted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    log.info("Inserted %d HCPCS codes from spending data", inserted)


# [EN] Load HCPCS codes from a reference CSV file with descriptions and categories.
#      Automatically detects column names by matching common patterns (e.g., "hcpcs_code",
#      "short_description", "long_description", "category").
#      Uses INSERT ... ON CONFLICT DO UPDATE with COALESCE to preserve existing descriptions.
# [RU] Загрузка кодов HCPCS из справочного CSV-файла с описаниями и категориями.
#      Автоматически определяет имена столбцов, сопоставляя распространённые шаблоны
#      (напр., "hcpcs_code", "short_description", "long_description", "category").
#      Использует INSERT ... ON CONFLICT DO UPDATE с COALESCE для сохранения существующих описаний.
# [PT] Carrega codigos HCPCS de um arquivo CSV de referencia com descricoes e categorias.
#      Detecta automaticamente nomes de colunas correspondendo padroes comuns (ex.: "hcpcs_code",
#      "short_description", "long_description", "category").
#      Usa INSERT ... ON CONFLICT DO UPDATE com COALESCE para preservar descricoes existentes.
# Parameters / Параметры / Parametros:
#   file_path (Path):    [EN] Path to HCPCS CSV file | [RU] Путь к CSV-файлу HCPCS | [PT] Caminho do arquivo CSV HCPCS
#   database_url (str):  [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_hcpcs_from_file(file_path: Path, database_url: str):
    """Load HCPCS codes from a reference CSV file."""
    log.info("Loading HCPCS codes from %s", file_path)
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    loaded = 0
    skipped = 0

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = None
            short_desc = None
            long_desc = None
            category = None

            # [EN] Try to match each column header to a known field by pattern matching
            #      This handles varying column names across different HCPCS file versions
            # [RU] Пробуем сопоставить каждый заголовок столбца с известным полем по шаблону
            #      Это обрабатывает различные имена столбцов в разных версиях файлов HCPCS
            # [PT] Tenta corresponder cada cabecalho de coluna a um campo conhecido por padrao
            #      Isso lida com nomes de colunas variados entre diferentes versoes de arquivos HCPCS
            for key in row:
                kl = key.lower().strip()
                if "hcpcs" in kl and "code" in kl:
                    code = row[key].strip()
                elif kl in ("code", "hcpc"):
                    code = row[key].strip()
                elif "short" in kl and "desc" in kl:
                    short_desc = row[key].strip()
                elif "long" in kl and "desc" in kl:
                    long_desc = row[key].strip()
                elif "desc" in kl and not short_desc:
                    short_desc = row[key].strip()
                elif "categ" in kl:
                    category = row[key].strip()

            # [EN] Skip row if no HCPCS code was found
            # [RU] Пропускаем строку, если код HCPCS не найден
            # [PT] Pula a linha se nenhum codigo HCPCS foi encontrado
            if not code:
                skipped += 1
                continue

            try:
                # [EN] Upsert: insert new code or update with COALESCE to keep existing descriptions
                #      if the new file has NULL for those fields
                # [RU] Upsert: вставляем новый код или обновляем с COALESCE для сохранения
                #      существующих описаний, если в новом файле эти поля пусты
                # [PT] Upsert: insere novo codigo ou atualiza com COALESCE para manter descricoes
                #      existentes se o novo arquivo tiver NULL para esses campos
                cur.execute(
                    """INSERT INTO hcpcs_codes (hcpcs_code, short_description, long_description, category)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (hcpcs_code) DO UPDATE SET
                        short_description = COALESCE(EXCLUDED.short_description, hcpcs_codes.short_description),
                        long_description = COALESCE(EXCLUDED.long_description, hcpcs_codes.long_description),
                        category = COALESCE(EXCLUDED.category, hcpcs_codes.category)""",
                    (code, short_desc or None, long_desc or None, category or None),
                )
                loaded += 1
            except Exception as e:
                log.debug("HCPCS insert error for %s: %s", code, e)
                conn.rollback()
                skipped += 1
                continue

    conn.commit()
    cur.close()
    conn.close()
    log.info("HCPCS load complete: %d loaded, %d skipped", loaded, skipped)


# [EN] Orchestrator function: decides whether to load HCPCS from a file or from the spending table.
#      First tries to find a reference file; if none exists, falls back to spending data.
# [RU] Функция-оркестратор: решает, загружать HCPCS из файла или из таблицы расходов.
#      Сначала пытается найти справочный файл; если не найден, использует данные расходов.
# [PT] Funcao orquestradora: decide se carrega HCPCS de um arquivo ou da tabela de gastos.
#      Primeiro tenta encontrar um arquivo de referencia; se nao existir, recorre aos dados de gastos.
# Parameters / Параметры / Parametros:
#   database_url (str | None): [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_hcpcs(database_url: str | None = None):
    """Load HCPCS codes from file or spending table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    hcpcs_file = find_hcpcs_file()
    if hcpcs_file:
        load_hcpcs_from_file(hcpcs_file, database_url)
    else:
        load_hcpcs_from_spending(database_url)


# [EN] Entry point: runs the HCPCS code load process
# [RU] Точка входа: запускает процесс загрузки кодов HCPCS
# [PT] Ponto de entrada: executa o processo de carga dos codigos HCPCS
def main():
    load_hcpcs()


if __name__ == "__main__":
    main()
