"""
[EN] Flask application factory for the Medicare Provider Spending dashboard.
     This module creates and configures the Flask app, initializes the database,
     and registers all route blueprints. It is the entry point of the application.

[RU] Фабрика приложения Flask для панели анализа расходов Medicare.
     Этот модуль создаёт и настраивает приложение Flask, инициализирует базу данных
     и регистрирует все маршрутные блюпринты. Это точка входа в приложение.

[PT] Fábrica de aplicação Flask para o painel de análise de gastos do Medicare.
     Este módulo cria e configura o aplicativo Flask, inicializa o banco de dados
     e registra todos os blueprints de rotas. É o ponto de entrada da aplicação.
"""

from flask import Flask

from app.config import Config


# [EN] Application factory function — creates a new Flask app instance each time it is called.
#      This pattern allows creating multiple app instances with different configs (e.g., for testing).
# [RU] Функция-фабрика приложения — создаёт новый экземпляр Flask при каждом вызове.
#      Этот паттерн позволяет создавать несколько экземпляров с разными конфигурациями (например, для тестов).
# [PT] Função fábrica da aplicação — cria uma nova instância do Flask a cada chamada.
#      Esse padrão permite criar múltiplas instâncias com diferentes configurações (ex.: para testes).
def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    # [EN] Load configuration values (DB URI, secret key, etc.) from the config class
    # [RU] Загрузить параметры конфигурации (URI базы данных, секретный ключ и т.д.) из класса конфигурации
    # [PT] Carregar valores de configuração (URI do banco, chave secreta, etc.) a partir da classe de configuração
    app.config.from_object(config_class)

    # [EN] Initialize the SQLAlchemy database extension with the Flask app
    # [RU] Инициализировать расширение базы данных SQLAlchemy для приложения Flask
    # [PT] Inicializar a extensão de banco de dados SQLAlchemy com o aplicativo Flask
    from app.models import db
    db.init_app(app)

    # [EN] Import and register all route blueprints.
    #      Each blueprint handles a separate section of the application (dashboard, providers, etc.).
    # [RU] Импортировать и зарегистрировать все маршрутные блюпринты.
    #      Каждый блюпринт отвечает за отдельный раздел приложения (панель, поставщики и т.д.).
    # [PT] Importar e registrar todos os blueprints de rotas.
    #      Cada blueprint gerencia uma seção separada da aplicação (painel, provedores, etc.).
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.providers import bp as providers_bp
    from app.routes.spending import bp as spending_bp
    from app.routes.addresses import bp as addresses_bp
    from app.routes.analysis import bp as analysis_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(providers_bp)
    app.register_blueprint(spending_bp)
    app.register_blueprint(addresses_bp)
    app.register_blueprint(analysis_bp)

    # [EN] Simple health-check endpoint — returns HTTP 200 with {"status": "ok"}.
    #      Used by load balancers and monitoring services to verify the app is running.
    # [RU] Простой эндпоинт проверки состояния — возвращает HTTP 200 с {"status": "ok"}.
    #      Используется балансировщиками нагрузки и мониторингом для проверки работоспособности приложения.
    # [PT] Endpoint simples de verificação de saúde — retorna HTTP 200 com {"status": "ok"}.
    #      Usado por balanceadores de carga e serviços de monitoramento para verificar se o app está funcionando.
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app
