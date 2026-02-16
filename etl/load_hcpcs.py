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


# [EN] Load HCPCS codes from CMS fixed-width HCPCS Alpha-Numeric file.
#      The CMS file uses a 320-character fixed-width record format:
#        Positions  1-5:   HCPCS code (5 chars)
#        Positions  6-10:  Sequence number (5 numeric)
#        Position   11:    Record ID code (1 char): 3=first procedure line, 4=continuation,
#                          7=first modifier line, 8=modifier continuation
#        Positions 12-91:  Long description (80 chars)
#        Positions 92-119: Short description (28 chars)
#      Only records with ID code '3' (first line of procedure) carry both descriptions.
#      Continuation records (ID '4') extend the long description but repeat the same code.
#      This function concatenates continuation lines into the full long description.
# [RU] Загрузка кодов HCPCS из файла CMS с фиксированной шириной (Alpha-Numeric).
#      Файл CMS использует формат записи с фиксированной шириной 320 символов:
#        Позиции  1-5:   Код HCPCS (5 символов)
#        Позиции  6-10:  Порядковый номер (5 цифр)
#        Позиция  11:    Код идентификации записи (1 символ): 3=первая строка процедуры,
#                        4=продолжение, 7=первая строка модификатора, 8=продолжение модификатора
#        Позиции 12-91:  Длинное описание (80 символов)
#        Позиции 92-119: Краткое описание (28 символов)
#      Только записи с кодом ID '3' содержат оба описания.
# [PT] Carrega codigos HCPCS do arquivo CMS de largura fixa (Alpha-Numeric).
#      O arquivo CMS usa formato de registro de largura fixa de 320 caracteres:
#        Posicoes  1-5:   Codigo HCPCS (5 caracteres)
#        Posicoes  6-10:  Numero de sequencia (5 numerico)
#        Posicao   11:    Codigo ID do registro (1 caractere): 3=primeira linha de procedimento,
#                         4=continuacao, 7=primeira linha de modificador, 8=continuacao de modificador
#        Posicoes 12-91:  Descricao longa (80 caracteres)
#        Posicoes 92-119: Descricao curta (28 caracteres)
#      Apenas registros com codigo ID '3' contem ambas as descricoes.
# Parameters / Параметры / Parametros:
#   file_path (Path):    [EN] Path to CMS fixed-width HCPCS file | [RU] Путь к файлу HCPCS CMS | [PT] Caminho do arquivo HCPCS CMS
#   database_url (str):  [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_hcpcs_from_cms_fixed_width(file_path: Path, database_url: str):
    """Load HCPCS codes from CMS fixed-width Alpha-Numeric file."""
    log.info("Loading HCPCS codes from CMS fixed-width file: %s", file_path)
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    loaded = 0
    skipped = 0

    # [EN] First pass: collect all codes with their descriptions.
    #      Record type '3' = first line of a procedure record (has short desc in pos 92-119).
    #      Record type '4' = continuation of long description (no short desc).
    #      We concatenate continuation lines to build the full long description.
    # [RU] Первый проход: собираем все коды с описаниями.
    #      Тип записи '3' = первая строка процедуры (краткое описание в поз. 92-119).
    #      Тип записи '4' = продолжение длинного описания (без краткого описания).
    #      Объединяем строки продолжения для построения полного длинного описания.
    # [PT] Primeira passagem: coleta todos os codigos com suas descricoes.
    #      Tipo de registro '3' = primeira linha de procedimento (descricao curta na pos 92-119).
    #      Tipo de registro '4' = continuacao da descricao longa (sem descricao curta).
    #      Concatenamos linhas de continuacao para construir a descricao longa completa.
    codes = {}  # hcpcs_code -> {short_desc, long_desc}

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            # [EN] Skip lines shorter than the minimum meaningful length
            # [RU] Пропускаем строки короче минимальной значимой длины
            # [PT] Pula linhas mais curtas que o comprimento minimo significativo
            if len(line.rstrip()) < 11:
                continue

            # [EN] Extract fixed-width fields (0-indexed in Python, 1-indexed in spec)
            # [RU] Извлекаем поля фиксированной ширины (0-индексация в Python, 1-индексация в спецификации)
            # [PT] Extrai campos de largura fixa (indexado em 0 em Python, indexado em 1 na especificacao)
            hcpcs_code = line[0:5].strip()       # Positions 1-5
            record_id = line[10]                  # Position 11
            long_desc_part = line[11:91].strip()  # Positions 12-91

            if not hcpcs_code:
                continue

            if record_id == "3":
                # [EN] First line of procedure record — extract both descriptions
                # [RU] Первая строка записи процедуры — извлекаем оба описания
                # [PT] Primeira linha do registro de procedimento — extrai ambas as descricoes
                short_desc = line[91:119].strip() if len(line) >= 119 else ""
                codes[hcpcs_code] = {
                    "short_desc": short_desc or None,
                    "long_desc": long_desc_part,
                }
            elif record_id == "4":
                # [EN] Continuation of long description — append to existing code
                # [RU] Продолжение длинного описания — добавляем к существующему коду
                # [PT] Continuacao da descricao longa — anexa ao codigo existente
                if hcpcs_code in codes and long_desc_part:
                    codes[hcpcs_code]["long_desc"] += " " + long_desc_part
            # [EN] Record types '7' and '8' are modifier records — skip for now
            #      (we only need procedure codes for the dashboard)
            # [RU] Типы записей '7' и '8' — записи модификаторов, пропускаем
            # [PT] Tipos de registro '7' e '8' sao registros de modificadores — pulamos

    log.info("Parsed %d unique procedure codes from CMS file", len(codes))

    # [EN] Second pass: upsert all codes into the database
    # [RU] Второй проход: upsert всех кодов в базу данных
    # [PT] Segunda passagem: upsert de todos os codigos no banco de dados
    for hcpcs_code, desc in codes.items():
        short_desc = desc["short_desc"]
        long_desc = desc["long_desc"].strip() if desc["long_desc"] else None

        try:
            cur.execute(
                """INSERT INTO hcpcs_codes (hcpcs_code, short_description, long_description)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (hcpcs_code) DO UPDATE SET
                    short_description = COALESCE(EXCLUDED.short_description, hcpcs_codes.short_description),
                    long_description = COALESCE(EXCLUDED.long_description, hcpcs_codes.long_description)""",
                (hcpcs_code, short_desc, long_desc),
            )
            loaded += 1
        except Exception as e:
            log.debug("HCPCS insert error for %s: %s", hcpcs_code, e)
            conn.rollback()
            skipped += 1
            continue

    conn.commit()
    cur.close()
    conn.close()
    log.info("HCPCS CMS load complete: %d loaded, %d skipped", loaded, skipped)


# [EN] Search for a CMS fixed-width HCPCS file in raw_data/hcpcs_ref/ directory.
#      Looks for files matching the CMS naming pattern (e.g., HCPC2026_JAN_ANWEB_*.txt).
# [RU] Поиск файла CMS HCPCS с фиксированной шириной в директории raw_data/hcpcs_ref/.
#      Ищет файлы, соответствующие шаблону именования CMS (напр., HCPC2026_JAN_ANWEB_*.txt).
# [PT] Busca arquivo CMS HCPCS de largura fixa no diretorio raw_data/hcpcs_ref/.
#      Procura arquivos correspondentes ao padrao de nomeacao CMS (ex.: HCPC2026_JAN_ANWEB_*.txt).
# Returns / Возвращает / Retorna:
#   Path | None: [EN] Path to CMS file or None | [RU] Путь к файлу CMS или None | [PT] Caminho do arquivo CMS ou None
def find_cms_hcpcs_file() -> Path | None:
    """Find CMS fixed-width HCPCS file in raw_data/hcpcs_ref/."""
    hcpcs_ref_dir = RAW_DATA_DIR / "hcpcs_ref"
    if not hcpcs_ref_dir.exists():
        return None
    # [EN] Search for CMS HCPCS files matching known naming patterns
    # [RU] Поиск файлов CMS HCPCS по известным шаблонам именования
    # [PT] Busca arquivos CMS HCPCS por padroes de nomeacao conhecidos
    for pattern in ["HCPC*_ANWEB_*.txt", "HCPC*_anweb_*.txt", "HCPC*.txt"]:
        candidates = list(hcpcs_ref_dir.glob(pattern))
        if candidates:
            # [EN] Return the most recently modified file if multiple match
            # [RU] Возвращаем последний модифицированный файл, если совпадений несколько
            # [PT] Retorna o arquivo modificado mais recentemente se houver multiplas correspondencias
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


# [EN] Orchestrator function: decides whether to load HCPCS from a file or from the spending table.
#      Priority: 1) CMS fixed-width file in raw_data/hcpcs_ref/
#                2) CSV/TSV reference file in raw_data/
#                3) Fallback to extracting codes from spending table (no descriptions)
# [RU] Функция-оркестратор: решает, загружать HCPCS из файла или из таблицы расходов.
#      Приоритет: 1) Файл CMS с фиксированной шириной в raw_data/hcpcs_ref/
#                 2) CSV/TSV справочный файл в raw_data/
#                 3) Запасной вариант — извлечение кодов из таблицы расходов (без описаний)
# [PT] Funcao orquestradora: decide se carrega HCPCS de um arquivo ou da tabela de gastos.
#      Prioridade: 1) Arquivo CMS de largura fixa em raw_data/hcpcs_ref/
#                  2) Arquivo de referencia CSV/TSV em raw_data/
#                  3) Fallback para extracao de codigos da tabela de gastos (sem descricoes)
# Parameters / Параметры / Parametros:
#   database_url (str | None): [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
def load_hcpcs(database_url: str | None = None):
    """Load HCPCS codes from CMS file, CSV file, or spending table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    # [EN] Priority 1: CMS fixed-width file (best source — has both short and long descriptions)
    # [RU] Приоритет 1: Файл CMS с фиксированной шириной (лучший источник — оба описания)
    # [PT] Prioridade 1: Arquivo CMS de largura fixa (melhor fonte — ambas as descricoes)
    cms_file = find_cms_hcpcs_file()
    if cms_file:
        load_hcpcs_from_cms_fixed_width(cms_file, database_url)
        return

    # [EN] Priority 2: CSV/TSV reference file
    # [RU] Приоритет 2: CSV/TSV справочный файл
    # [PT] Prioridade 2: Arquivo de referencia CSV/TSV
    hcpcs_file = find_hcpcs_file()
    if hcpcs_file:
        load_hcpcs_from_file(hcpcs_file, database_url)
    else:
        # [EN] Priority 3: Fallback — extract codes from spending table (no descriptions)
        # [RU] Приоритет 3: Запасной вариант — извлечение кодов из таблицы расходов (без описаний)
        # [PT] Prioridade 3: Fallback — extrai codigos da tabela de gastos (sem descricoes)
        load_hcpcs_from_spending(database_url)


# [EN] Entry point: runs the HCPCS code load process
# [RU] Точка входа: запускает процесс загрузки кодов HCPCS
# [PT] Ponto de entrada: executa o processo de carga dos codigos HCPCS
def main():
    load_hcpcs()


if __name__ == "__main__":
    main()
