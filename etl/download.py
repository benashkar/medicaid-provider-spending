"""Download HHS Medicaid Provider Spending and NPPES NPI Registry data files."""

import hashlib
import logging
import os
import sys
import zipfile
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"

# HHS Medicaid Provider Spending dataset
HHS_URL = (
    "https://data.medicaid.gov/api/1/datastore/query/"
    "4e6c7966-0452-5a67-91a1-1bcf53b6f49a/0/download?format=csv"
)
HHS_FILENAME = "medicaid_provider_spending.csv"

# NPPES NPI Registry full replacement file
NPPES_URL = "https://download.cms.gov/nppes/NPPES_Data_Dissemination_December_2024.zip"
NPPES_FILENAME = "NPPES_Data_Dissemination.zip"


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> Path:
    """Stream-download a file with progress logging."""
    log.info("Downloading %s → %s", url[:80], dest.name)
    dest.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

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


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file for integrity verification."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_zip(zip_path: Path, dest_dir: Path) -> list[str]:
    """Extract a ZIP file and return the list of extracted filenames."""
    log.info("Extracting %s → %s", zip_path.name, dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
        names = zf.namelist()
    log.info("Extracted %d files", len(names))
    return names


def download_hhs(force: bool = False) -> Path:
    """Download the HHS Medicaid Provider Spending CSV."""
    dest = RAW_DATA_DIR / HHS_FILENAME
    if dest.exists() and not force:
        log.info("HHS file already exists: %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
        return dest
    return download_file(HHS_URL, dest)


def download_nppes(force: bool = False) -> Path:
    """Download and extract the NPPES NPI Registry ZIP."""
    zip_dest = RAW_DATA_DIR / NPPES_FILENAME
    if zip_dest.exists() and not force:
        log.info("NPPES ZIP already exists: %s", zip_dest)
    else:
        download_file(NPPES_URL, zip_dest)

    # Extract
    nppes_dir = RAW_DATA_DIR / "nppes"
    nppes_dir.mkdir(exist_ok=True)
    extract_zip(zip_dest, nppes_dir)

    # Find the main CSV
    csvs = list(nppes_dir.glob("npidata_pfile_*.csv"))
    if csvs:
        log.info("Main NPPES CSV: %s", csvs[0].name)
    else:
        log.warning("Could not find main NPPES CSV in extracted files")

    return nppes_dir


def main():
    """Download all data sources."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    force = "--force" in sys.argv
    log.info("=== Downloading data sources ===")

    hhs_path = download_hhs(force=force)
    sha = sha256_file(hhs_path)
    log.info("HHS SHA-256: %s", sha)

    nppes_dir = download_nppes(force=force)
    log.info("NPPES data directory: %s", nppes_dir)

    log.info("=== All downloads complete ===")


if __name__ == "__main__":
    main()
