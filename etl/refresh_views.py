"""
Refresh all materialized views for the Medicaid Provider Spending dashboard.

[EN] This module refreshes all PostgreSQL materialized views used by the dashboard.
     Materialized views are pre-computed query results stored as tables for fast reads.
     After data is loaded or updated (spending, providers, addresses), these views must
     be refreshed to reflect the latest data. The module supports both standard and
     concurrent refresh modes. After refreshing, it reports row counts for verification.

[RU] Этот модуль обновляет все материализованные представления PostgreSQL, используемые панелью мониторинга.
     Материализованные представления -- это предвычисленные результаты запросов, хранящиеся как таблицы
     для быстрого чтения. После загрузки или обновления данных (расходы, поставщики, адреса) эти
     представления необходимо обновить для отражения актуальных данных. Модуль поддерживает как
     стандартное, так и конкурентное обновление. После обновления выводит количество строк для проверки.

[PT] Este modulo atualiza todas as views materializadas do PostgreSQL usadas pelo painel.
     Views materializadas sao resultados de consultas pre-computados armazenados como tabelas
     para leitura rapida. Apos os dados serem carregados ou atualizados (gastos, provedores,
     enderecos), essas views devem ser atualizadas para refletir os dados mais recentes.
     O modulo suporta tanto atualizacao padrao quanto concorrente. Apos a atualizacao,
     reporta a contagem de linhas para verificacao.
"""

import logging
import os
import sys

import psycopg2

# [EN] Configure logging with timestamp, log level, and message format
# [RU] Настройка логирования с меткой времени, уровнем и форматом сообщения
# [PT] Configuracao de logging com timestamp, nivel e formato de mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# [EN] Ordered list of materialized views to refresh.
#      Order matters: base summary views first, then analysis views that may depend on them.
#      The first four are core data summaries; the last six are analytical/dashboard views.
# [RU] Упорядоченный список материализованных представлений для обновления.
#      Порядок важен: сначала базовые сводные представления, затем аналитические, зависящие от них.
#      Первые четыре -- основные сводки данных; последние шесть -- аналитические представления.
# [PT] Lista ordenada de views materializadas para atualizar.
#      A ordem importa: primeiro as views de resumo base, depois as de analise que dependem delas.
#      As primeiras quatro sao resumos de dados basicos; as ultimas seis sao views analiticas.
MATERIALIZED_VIEWS = [
    "mv_provider_spending_summary",
    "mv_monthly_spending",
    "mv_state_spending",
    "mv_hcpcs_spending",
    # [EN] Analysis views (depend on base views and core tables)
    # [RU] Аналитические представления (зависят от базовых представлений и основных таблиц)
    # [PT] Views de analise (dependem das views base e tabelas principais)
    "mv_top_organizations",
    "mv_shared_addresses",
    "mv_spending_growth",
    "mv_outlier_providers",
    "mv_geographic_concentration",
    "mv_billing_servicing_network",
    # [EN] Fraud detection views (added in fraud detection suite)
    # [RU] Представления обнаружения мошенничества
    # [PT] Views de deteccao de fraude
    "mv_org_yoy_growth",
    "mv_address_clustering",
    "mv_rapid_ramp",
    "mv_fraud_risk_score",
    "mv_avg_claim_by_provider",
    "mv_official_network",
]


# [EN] Refresh all materialized views in the defined order, then report row counts.
#      - Standard refresh (default): locks the view during refresh, no reads until done
#      - Concurrent refresh (--concurrently flag): allows reads during refresh, but requires
#        a unique index on the view and takes longer
# [RU] Обновляет все материализованные представления в заданном порядке, затем выводит количество строк.
#      - Стандартное обновление (по умолчанию): блокирует представление во время обновления, чтение невозможно
#      - Конкурентное обновление (флаг --concurrently): позволяет чтение во время обновления,
#        но требует уникального индекса на представлении и занимает больше времени
# [PT] Atualiza todas as views materializadas na ordem definida, depois reporta contagem de linhas.
#      - Atualizacao padrao (default): bloqueia a view durante a atualizacao, sem leituras ate terminar
#      - Atualizacao concorrente (flag --concurrently): permite leituras durante a atualizacao,
#        mas requer indice unico na view e leva mais tempo
# Parameters / Параметры / Parametros:
#   database_url (str | None):  [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
#   concurrently (bool):        [EN] If True, use CONCURRENTLY refresh | [RU] Если True, используется конкурентное обновление | [PT] Se True, usa atualizacao CONCURRENTLY
def refresh_views(database_url: str | None = None, concurrently: bool = False):
    """Refresh all materialized views."""
    database_url = database_url or os.environ["DATABASE_URL"]

    # [EN] autocommit=True is required for REFRESH MATERIALIZED VIEW (DDL command)
    # [RU] autocommit=True необходим для REFRESH MATERIALIZED VIEW (DDL-команда)
    # [PT] autocommit=True e necessario para REFRESH MATERIALIZED VIEW (comando DDL)
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    log.info("=== Refreshing materialized views ===")

    # [EN] Refresh each view in order, logging success or failure for each
    # [RU] Обновляем каждое представление по порядку, логируя успех или ошибку для каждого
    # [PT] Atualiza cada view em ordem, registrando sucesso ou falha para cada uma
    for view_name in MATERIALIZED_VIEWS:
        try:
            if concurrently:
                # [EN] CONCURRENTLY allows reads during refresh but requires unique index
                # [RU] CONCURRENTLY позволяет чтение при обновлении, но требует уникального индекса
                # [PT] CONCURRENTLY permite leituras durante atualizacao, mas requer indice unico
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
            else:
                cur.execute(f"REFRESH MATERIALIZED VIEW {view_name}")
            log.info("Refreshed %s", view_name)
        except Exception as e:
            log.error("Failed to refresh %s: %s", view_name, e)

    # [EN] Report row counts for each view to verify refresh was successful
    # [RU] Выводим количество строк для каждого представления для проверки успешности обновления
    # [PT] Reporta contagem de linhas para cada view para verificar se a atualizacao foi bem-sucedida
    for view_name in MATERIALIZED_VIEWS:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {view_name}")
            count = cur.fetchone()[0]
            log.info("  %s: %d rows", view_name, count)
        except Exception as e:
            log.error("  %s: count failed — %s", view_name, e)

    cur.close()
    conn.close()
    log.info("=== View refresh complete ===")


# [EN] Entry point: refreshes all materialized views.
#      Pass --concurrently on the command line to use concurrent refresh mode.
# [RU] Точка входа: обновляет все материализованные представления.
#      Передайте --concurrently в командной строке для конкурентного режима обновления.
# [PT] Ponto de entrada: atualiza todas as views materializadas.
#      Passe --concurrently na linha de comando para usar o modo de atualizacao concorrente.
def main():
    # [EN] Check for --concurrently flag in command-line arguments
    # [RU] Проверка наличия флага --concurrently в аргументах командной строки
    # [PT] Verifica o flag --concurrently nos argumentos da linha de comando
    concurrently = "--concurrently" in sys.argv
    refresh_views(concurrently=concurrently)


if __name__ == "__main__":
    main()
