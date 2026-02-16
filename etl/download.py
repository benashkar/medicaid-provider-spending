"""
Download HHS Medicaid Provider Spending and NPPES NPI Registry data files.

[EN] This module downloads two primary data sources for the Medicare Provider Spending project:
     1) HHS Medicaid Provider Spending CSV (claims data with billing/servicing NPIs and HCPCS codes)
     2) NPPES NPI Registry (provider demographic and taxonomy information)
     It supports resumable downloads, SHA-256 integrity verification, and ZIP extraction.

[RU] Этот модуль загружает два основных источника данных для проекта Medicare Provider Spending:
     1) CSV-файл расходов поставщиков HHS Medicaid (данные о заявках с NPI и кодами HCPCS)
     2) Реестр NPI NPPES (демографическая информация и таксономия поставщиков)
     Поддерживает потоковую загрузку, проверку целостности SHA-256 и распаковку ZIP-архивов.

[PT] Este modulo faz o download de duas fontes de dados principais para o projeto Medicare Provider Spending:
     1) CSV de gastos de provedores HHS Medicaid (dados de reivindicacoes com NPIs e codigos HCPCS)
     2) Registro NPI do NPPES (informacoes demograficas e de taxonomia dos provedores)
     Suporta download em streaming, verificacao de integridade SHA-256 e extracao de arquivos ZIP.
"""

import hashlib
import logging
import os
import sys
import zipfile
from pathlib import Path

import requests

# [EN] Configure logging with timestamp, log level, and message format
# [RU] Настройка логирования с меткой времени, уровнем и форматом сообщения
# [PT] Configuracao de logging com timestamp, nivel e formato de mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# [EN] Base directory for all raw data files (one level up from etl/, then into raw_data/)
# [RU] Базовая директория для всех необработанных файлов данных (на уровень выше etl/, затем в raw_data/)
# [PT] Diretorio base para todos os arquivos de dados brutos (um nivel acima de etl/, depois em raw_data/)
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"

# [EN] HHS Medicaid Provider Spending dataset URL and filenames (moved to opendata.hhs.gov Feb 2026)
# [RU] URL и имена файлов набора данных о расходах поставщиков HHS Medicaid (перенесён на opendata.hhs.gov в фев. 2026)
# [PT] URL e nomes de arquivo do conjunto de dados de gastos de provedores HHS Medicaid (movido para opendata.hhs.gov em fev. 2026)
HHS_URL = (
    "https://stopendataprod.blob.core.windows.net/datasets/"
    "medicaid-provider-spending/2026-02-09/medicaid-provider-spending.csv.zip"
)
HHS_FILENAME = "medicaid_provider_spending.csv.zip"
HHS_CSV_FILENAME = "medicaid-provider-spending.csv"

# [EN] NPPES NPI Registry full replacement file URL and filename
# [RU] URL и имя файла полной замены реестра NPI NPPES
# [PT] URL e nome do arquivo de substituicao completa do registro NPI NPPES
NPPES_URL = "https://download.cms.gov/nppes/NPPES_Data_Dissemination_February_2026.zip"
NPPES_FILENAME = "NPPES_Data_Dissemination.zip"


# [EN] Download a file from a URL to a local path with streaming and progress logging.
#      Streams data in chunks to avoid loading the entire file into memory at once.
# [RU] Загрузка файла по URL в локальный путь с потоковой передачей и логированием прогресса.
#      Данные передаются по частям, чтобы не загружать весь файл в память сразу.
# [PT] Faz download de um arquivo de uma URL para um caminho local com streaming e log de progresso.
#      Os dados sao transmitidos em blocos para evitar carregar o arquivo inteiro na memoria.
# Parameters / Параметры / Parametros:
#   url (str):        [EN] Source URL | [RU] URL источника | [PT] URL de origem
#   dest (Path):      [EN] Destination file path | [RU] Путь к файлу назначения | [PT] Caminho do arquivo destino
#   chunk_size (int): [EN] Bytes per chunk (default 8192) | [RU] Байт на блок (по умолч. 8192) | [PT] Bytes por bloco (padrao 8192)
# Returns / Возвращает / Retorna:
#   Path: [EN] Path to the downloaded file | [RU] Путь к загруженному файлу | [PT] Caminho do arquivo baixado
def download_file(url: str, dest: Path, chunk_size: int = 8192) -> Path:
    """Stream-download a file with progress logging."""
    log.info("Downloading %s → %s", url[:80], dest.name)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # [EN] Open an HTTP GET request with streaming enabled and a 60-second timeout
    # [RU] Открываем HTTP GET-запрос с потоковой передачей и таймаутом 60 секунд
    # [PT] Abre uma requisicao HTTP GET com streaming habilitado e timeout de 60 segundos
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    # [EN] Get total file size from response headers (0 if not provided by server)
    # [RU] Получаем общий размер файла из заголовков ответа (0, если сервер не указал)
    # [PT] Obtem o tamanho total do arquivo dos cabecalhos da resposta (0 se nao fornecido pelo servidor)
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    # [EN] Write data chunk by chunk to disk, logging progress periodically
    # [RU] Записываем данные по частям на диск, периодически логируя прогресс
    # [PT] Escreve os dados bloco por bloco no disco, registrando o progresso periodicamente
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                if downloaded % (50 * chunk_size) == 0:
                    log.info("  %.1f%% (%d / %d bytes)", pct, downloaded, total)

    log.info("Download complete: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


# [EN] Compute SHA-256 hash of a file for data integrity verification.
#      Reads the file in 8KB chunks to handle large files efficiently.
# [RU] Вычисляет хеш SHA-256 файла для проверки целостности данных.
#      Читает файл блоками по 8 КБ для эффективной обработки больших файлов.
# [PT] Calcula o hash SHA-256 de um arquivo para verificacao de integridade dos dados.
#      Le o arquivo em blocos de 8 KB para lidar eficientemente com arquivos grandes.
# Parameters / Параметры / Parametros:
#   path (Path): [EN] Path to file | [RU] Путь к файлу | [PT] Caminho do arquivo
# Returns / Возвращает / Retorna:
#   str: [EN] Hex-encoded SHA-256 hash | [RU] SHA-256 хеш в hex-формате | [PT] Hash SHA-256 em formato hexadecimal
def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file for integrity verification."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# [EN] Extract all files from a ZIP archive to a destination directory.
# [RU] Извлекает все файлы из ZIP-архива в указанную директорию.
# [PT] Extrai todos os arquivos de um arquivo ZIP para um diretorio de destino.
# Parameters / Параметры / Parametros:
#   zip_path (Path): [EN] Path to ZIP file | [RU] Путь к ZIP-файлу | [PT] Caminho do arquivo ZIP
#   dest_dir (Path): [EN] Extraction directory | [RU] Директория для извлечения | [PT] Diretorio de extracao
# Returns / Возвращает / Retorna:
#   list[str]: [EN] List of extracted filenames | [RU] Список имён извлечённых файлов | [PT] Lista de nomes dos arquivos extraidos
def extract_zip(zip_path: Path, dest_dir: Path) -> list[str]:
    """Extract a ZIP file and return the list of extracted filenames."""
    log.info("Extracting %s → %s", zip_path.name, dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
        names = zf.namelist()
    log.info("Extracted %d files", len(names))
    return names


# [EN] Download and extract the HHS Medicaid Provider Spending CSV.
#      Skips download if the CSV already exists (unless force=True).
#      Downloads the ZIP, extracts it, and returns the path to the CSV.
# [RU] Загружает и распаковывает CSV-файл расходов поставщиков HHS Medicaid.
#      Пропускает загрузку, если CSV уже существует (если не указан force=True).
#      Загружает ZIP, извлекает его и возвращает путь к CSV.
# [PT] Faz download e extrai o CSV de gastos de provedores HHS Medicaid.
#      Pula o download se o CSV ja existe (a menos que force=True).
#      Baixa o ZIP, extrai e retorna o caminho do CSV.
# Parameters / Параметры / Parametros:
#   force (bool): [EN] Re-download even if file exists | [RU] Перезагрузить даже если файл существует | [PT] Re-baixar mesmo se o arquivo ja existir
# Returns / Возвращает / Retorna:
#   Path: [EN] Path to the spending CSV | [RU] Путь к CSV расходов | [PT] Caminho do CSV de gastos
def download_hhs(force: bool = False) -> Path:
    """Download and extract the HHS Medicaid Provider Spending CSV."""
    csv_dest = RAW_DATA_DIR / HHS_CSV_FILENAME
    if csv_dest.exists() and not force:
        log.info("HHS CSV already exists: %s (%.1f MB)", csv_dest, csv_dest.stat().st_size / 1e6)
        return csv_dest

    zip_dest = RAW_DATA_DIR / HHS_FILENAME
    if not zip_dest.exists() or force:
        download_file(HHS_URL, zip_dest)

    # [EN] Extract CSV from ZIP archive
    # [RU] Извлечение CSV из ZIP-архива
    # [PT] Extracao do CSV do arquivo ZIP
    log.info("Extracting HHS spending CSV from ZIP...")
    extract_zip(zip_dest, RAW_DATA_DIR)

    if csv_dest.exists():
        log.info("HHS CSV extracted: %s (%.1f MB)", csv_dest, csv_dest.stat().st_size / 1e6)
    else:
        # [EN] Fallback: search for any matching CSV if expected filename wasn't found
        # [RU] Запасной вариант: поиск любого подходящего CSV, если ожидаемое имя файла не найдено
        # [PT] Fallback: busca qualquer CSV correspondente se o nome esperado nao foi encontrado
        csvs = list(RAW_DATA_DIR.glob("medicaid*.csv"))
        if csvs:
            log.info("Extracted CSV found: %s", csvs[0].name)
            return csvs[0]
        log.warning("Could not find extracted HHS CSV")

    return csv_dest


# [EN] Download and extract the NPPES NPI Registry ZIP file.
#      The NPPES file contains provider demographic data (names, addresses, taxonomies).
#      Skips download if the ZIP already exists (unless force=True).
# [RU] Загружает и распаковывает ZIP-файл реестра NPI NPPES.
#      Файл NPPES содержит демографические данные поставщиков (имена, адреса, таксономии).
#      Пропускает загрузку, если ZIP уже существует (если не указан force=True).
# [PT] Faz download e extrai o arquivo ZIP do registro NPI NPPES.
#      O arquivo NPPES contem dados demograficos dos provedores (nomes, enderecos, taxonomias).
#      Pula o download se o ZIP ja existe (a menos que force=True).
# Parameters / Параметры / Parametros:
#   force (bool): [EN] Re-download even if file exists | [RU] Перезагрузить даже если файл существует | [PT] Re-baixar mesmo se ja existir
# Returns / Возвращает / Retorna:
#   Path: [EN] Path to the extracted NPPES directory | [RU] Путь к директории с извлечёнными данными NPPES | [PT] Caminho do diretorio com os dados extraidos do NPPES
def download_nppes(force: bool = False) -> Path:
    """Download and extract the NPPES NPI Registry ZIP."""
    zip_dest = RAW_DATA_DIR / NPPES_FILENAME
    if zip_dest.exists() and not force:
        log.info("NPPES ZIP already exists: %s", zip_dest)
    else:
        download_file(NPPES_URL, zip_dest)

    # [EN] Extract into a dedicated nppes/ subdirectory
    # [RU] Извлечение в отдельную поддиректорию nppes/
    # [PT] Extracao para o subdiretorio dedicado nppes/
    nppes_dir = RAW_DATA_DIR / "nppes"
    nppes_dir.mkdir(exist_ok=True)
    extract_zip(zip_dest, nppes_dir)

    # [EN] Find the main NPPES CSV (the largest file matching the naming pattern)
    # [RU] Поиск основного CSV-файла NPPES (крупнейший файл, соответствующий шаблону имени)
    # [PT] Busca o CSV principal do NPPES (o maior arquivo que corresponde ao padrao de nome)
    csvs = list(nppes_dir.glob("npidata_pfile_*.csv"))
    if csvs:
        log.info("Main NPPES CSV: %s", csvs[0].name)
    else:
        log.warning("Could not find main NPPES CSV in extracted files")

    return nppes_dir


# [EN] Main entry point: downloads all data sources (HHS spending + NPPES registry).
#      Pass --force on the command line to re-download even if files already exist.
# [RU] Главная точка входа: загружает все источники данных (расходы HHS + реестр NPPES).
#      Передайте --force в командной строке для повторной загрузки, даже если файлы уже существуют.
# [PT] Ponto de entrada principal: faz download de todas as fontes de dados (gastos HHS + registro NPPES).
#      Passe --force na linha de comando para re-baixar mesmo se os arquivos ja existirem.
def main():
    """Download all data sources."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # [EN] Check command-line args for --force flag to override existing files
    # [RU] Проверка аргументов командной строки на наличие флага --force для перезаписи существующих файлов
    # [PT] Verifica os argumentos da linha de comando para o flag --force que sobrescreve arquivos existentes
    force = "--force" in sys.argv
    log.info("=== Downloading data sources ===")

    # [EN] Download HHS spending data and compute its SHA-256 hash for verification
    # [RU] Загрузка данных о расходах HHS и вычисление хеша SHA-256 для проверки
    # [PT] Download dos dados de gastos HHS e calculo do hash SHA-256 para verificacao
    hhs_path = download_hhs(force=force)
    sha = sha256_file(hhs_path)
    log.info("HHS SHA-256: %s", sha)

    # [EN] Download NPPES registry data
    # [RU] Загрузка данных реестра NPPES
    # [PT] Download dos dados do registro NPPES
    nppes_dir = download_nppes(force=force)
    log.info("NPPES data directory: %s", nppes_dir)

    log.info("=== All downloads complete ===")


if __name__ == "__main__":
    main()
