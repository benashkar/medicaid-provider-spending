"""
[EN] Flask configuration loaded from environment variables.
     Contains database connection settings, secret keys, and connection pool options.
     Values are read from a .env file via python-dotenv.

[RU] Конфигурация Flask, загружаемая из переменных окружения.
     Содержит настройки подключения к базе данных, секретные ключи и параметры пула соединений.
     Значения считываются из файла .env с помощью python-dotenv.

[PT] Configuração do Flask carregada a partir de variáveis de ambiente.
     Contém configurações de conexão com o banco de dados, chaves secretas e opções de pool de conexões.
     Os valores são lidos de um arquivo .env via python-dotenv.
"""

import os

from dotenv import load_dotenv

# [EN] Load environment variables from a .env file into os.environ.
#      This must be called before accessing any env vars below.
# [RU] Загрузить переменные окружения из файла .env в os.environ.
#      Это необходимо вызвать до обращения к переменным окружения ниже.
# [PT] Carregar variáveis de ambiente do arquivo .env para os.environ.
#      Isso deve ser chamado antes de acessar qualquer variável de ambiente abaixo.
load_dotenv()


# [EN] Configuration class that Flask reads via app.config.from_object().
#      All attributes become Flask config keys (e.g., app.config["SECRET_KEY"]).
# [RU] Класс конфигурации, который Flask читает через app.config.from_object().
#      Все атрибуты становятся ключами конфигурации Flask (например, app.config["SECRET_KEY"]).
# [PT] Classe de configuração que o Flask lê via app.config.from_object().
#      Todos os atributos se tornam chaves de configuração do Flask (ex.: app.config["SECRET_KEY"]).
class Config:
    # [EN] Secret key for session signing and CSRF protection. Use a strong random value in production.
    # [RU] Секретный ключ для подписи сессий и защиты от CSRF. В продакшене используйте надёжное случайное значение.
    # [PT] Chave secreta para assinatura de sessão e proteção CSRF. Use um valor aleatório forte em produção.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # [EN] Database connection URI (e.g., postgresql://user:pass@host/dbname)
    # [RU] URI подключения к базе данных (например, postgresql://user:pass@host/dbname)
    # [PT] URI de conexão com o banco de dados (ex.: postgresql://user:pass@host/dbname)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")

    # [EN] Disable SQLAlchemy event tracking to save memory (not needed in this app)
    # [RU] Отключить отслеживание событий SQLAlchemy для экономии памяти (в этом приложении не нужно)
    # [PT] Desativar rastreamento de eventos do SQLAlchemy para economizar memória (não necessário nesta aplicação)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # [EN] Database connection pool settings:
    #      - pool_size: max number of persistent connections (5)
    #      - pool_recycle: recycle connections after 300 seconds to avoid stale connections
    #      - pool_pre_ping: test connections before use to detect dropped connections
    # [RU] Настройки пула подключений к базе данных:
    #      - pool_size: максимальное количество постоянных соединений (5)
    #      - pool_recycle: обновлять соединения через 300 секунд, чтобы избежать устаревших соединений
    #      - pool_pre_ping: проверять соединения перед использованием для обнаружения разорванных соединений
    # [PT] Configurações do pool de conexões com o banco de dados:
    #      - pool_size: número máximo de conexões persistentes (5)
    #      - pool_recycle: reciclar conexões após 300 segundos para evitar conexões obsoletas
    #      - pool_pre_ping: testar conexões antes do uso para detectar conexões interrompidas
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # [EN] MySQL connection via PyMySQL driver for db99 RDS
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://") or SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
        # Legacy Postgres URL detected — should be updated to mysql+pymysql://
        pass
