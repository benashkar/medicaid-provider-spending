"""Secret loading: AWS Secrets Manager first, .env fallback for local dev."""

import json
import os

import boto3
from dotenv import load_dotenv


_cached_config = None


def _load_config():
    """Load DB credentials from AWS Secrets Manager, fall back to .env."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret = client.get_secret_value(SecretId='/ben/ai-tool/db99')
        creds = json.loads(secret['SecretString'])
        db_host = creds.get('DB_HOST') or ''
        db_port = creds.get('DB_PORT') or '3306'
        db_user = creds.get('DB_USER') or ''
        db_password = creds.get('DB_PASSWORD') or ''
        _cached_config = {
            'DB_HOST': db_host,
            'DB_PORT': db_port,
            'DB_USER': db_user,
            'DB_PASSWORD': db_password,
            '_source': 'aws',
        }
    except Exception:
        load_dotenv()
        _cached_config = {
            'DB_HOST': os.getenv('DB_HOST', ''),
            'DB_PORT': os.getenv('DB_PORT', '3306'),
            'DB_USER': os.getenv('DB_USER', ''),
            'DB_PASSWORD': os.getenv('DB_PASSWORD', ''),
            '_source': 'env',
        }

    # DB_NAME comes from env var (project-specific, not a secret)
    _cached_config['DB_NAME'] = os.getenv('DB_NAME', 'medicaid_spending')
    # Allow env var override for DB_HOST (e.g. direct IP for VPN sessions)
    if os.getenv('DB_HOST'):
        _cached_config['DB_HOST'] = os.getenv('DB_HOST')

    return _cached_config


def _build_database_url():
    """Build mysql+pymysql:// connection string from config."""
    cfg = _load_config()
    user = cfg['DB_USER']
    password = cfg['DB_PASSWORD']
    host = cfg['DB_HOST']
    port = cfg['DB_PORT']
    db_name = cfg['DB_NAME']
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }
