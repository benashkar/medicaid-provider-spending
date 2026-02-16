"""
Post-load validation queries for Medicaid Provider Spending database.

[EN] This module runs a series of validation queries after all ETL steps are complete.
     Each query checks a specific aspect of data quality:
     - Row counts: ensures tables are not empty
     - Date ranges: verifies spending data covers expected time periods
     - Referential integrity: detects orphan NPIs (in spending but missing from providers)
     - Data completeness: checks address parse rates and state distribution
     Some queries have pass/fail thresholds (check functions); others are informational only.
     Returns True if all threshold-based validations pass, False otherwise.

[RU] Этот модуль выполняет серию валидационных запросов после завершения всех этапов ETL.
     Каждый запрос проверяет определённый аспект качества данных:
     - Количество строк: убеждается, что таблицы не пусты
     - Диапазоны дат: проверяет, что данные расходов охватывают ожидаемые периоды
     - Ссылочная целостность: обнаруживает сиротские NPI (в расходах, но отсутствуют в поставщиках)
     - Полнота данных: проверяет долю разобранных адресов и распределение по штатам
     Некоторые запросы имеют пороги прохождения/провала (функции проверки); другие -- только информационные.
     Возвращает True, если все пороговые проверки пройдены, False в противном случае.

[PT] Este modulo executa uma serie de consultas de validacao apos todas as etapas ETL serem concluidas.
     Cada consulta verifica um aspecto especifico da qualidade dos dados:
     - Contagem de linhas: garante que as tabelas nao estao vazias
     - Intervalos de datas: verifica se os dados de gastos cobrem periodos esperados
     - Integridade referencial: detecta NPIs orfaos (em gastos mas ausentes em provedores)
     - Completude dos dados: verifica taxas de analise de enderecos e distribuicao por estado
     Algumas consultas tem limiares de aprovacao/reprovacao (funcoes de verificacao); outras sao apenas informativas.
     Retorna True se todas as validacoes com limiar passarem, False caso contrario.
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


# [EN] List of validation queries. Each entry is a tuple of:
#      (name, SQL query, check_function_or_None, description)
#      - name: short label for the validation
#      - SQL query: the query to execute
#      - check_function: a lambda that takes the result and returns True/False, or None for info-only
#      - description: human-readable explanation shown on failure
# [RU] Список валидационных запросов. Каждый элемент -- кортеж:
#      (имя, SQL-запрос, функция_проверки_или_None, описание)
#      - имя: краткая метка проверки
#      - SQL-запрос: запрос для выполнения
#      - функция_проверки: лямбда, принимающая результат и возвращающая True/False, или None для информационных
#      - описание: понятное объяснение, показываемое при неудаче
# [PT] Lista de consultas de validacao. Cada entrada e uma tupla:
#      (nome, consulta SQL, funcao_de_verificacao_ou_None, descricao)
#      - nome: rotulo curto para a validacao
#      - consulta SQL: a consulta a executar
#      - funcao_de_verificacao: lambda que recebe o resultado e retorna True/False, ou None para apenas informativo
#      - descricao: explicacao legivel mostrada em caso de falha
VALIDATION_QUERIES = [
    # [EN] Core table row counts — all must have data
    # [RU] Количество строк в основных таблицах — все должны содержать данные
    # [PT] Contagem de linhas das tabelas principais — todas devem ter dados
    (
        "Spending row count",
        "SELECT COUNT(*) FROM spending",
        lambda x: x > 0,
        "Spending table should have data",
    ),
    (
        "Provider count",
        "SELECT COUNT(*) FROM providers",
        lambda x: x > 0,
        "Providers table should have data",
    ),
    (
        "Address count",
        "SELECT COUNT(*) FROM addresses",
        lambda x: x > 0,
        "Addresses table should have data",
    ),
    (
        "Taxonomy count",
        "SELECT COUNT(*) FROM provider_taxonomies",
        lambda x: x > 0,
        "Taxonomies table should have data",
    ),
    (
        "HCPCS code count",
        "SELECT COUNT(*) FROM hcpcs_codes",
        lambda x: x > 0,
        "HCPCS codes table should have data",
    ),
    # [EN] Informational queries — no pass/fail threshold, just report values
    # [RU] Информационные запросы — без порога прохождения/провала, только вывод значений
    # [PT] Consultas informativas — sem limiar de aprovacao/reprovacao, apenas reporta valores
    (
        "Spending date range",
        "SELECT MIN(claim_month), MAX(claim_month) FROM spending",
        None,
        "Show spending date range",
    ),
    (
        "Unique billing NPIs in spending",
        "SELECT COUNT(DISTINCT billing_npi) FROM spending",
        None,
        "Count of unique billing providers",
    ),
    (
        "Unique servicing NPIs in spending",
        "SELECT COUNT(DISTINCT servicing_npi) FROM spending",
        None,
        "Count of unique servicing providers",
    ),
    # [EN] Financial sanity check — total paid should be positive
    # [RU] Финансовая проверка на здравость — общая оплата должна быть положительной
    # [PT] Verificacao de sanidade financeira — total pago deve ser positivo
    (
        "Total paid amount",
        "SELECT SUM(total_paid)::NUMERIC(20,2) FROM spending",
        lambda x: x > 0,
        "Total spending should be positive",
    ),
    # [EN] Referential integrity checks — detect orphan NPIs (in spending but not in providers)
    # [RU] Проверки ссылочной целостности — обнаружение сиротских NPI (в расходах, но не в поставщиках)
    # [PT] Verificacoes de integridade referencial — detecta NPIs orfaos (em gastos mas nao em provedores)
    (
        "Orphan billing NPIs (not in providers table)",
        """SELECT COUNT(DISTINCT s.billing_npi)
           FROM spending s
           LEFT JOIN providers p ON p.npi = s.billing_npi
           WHERE p.npi IS NULL""",
        None,
        "Billing NPIs missing from providers table",
    ),
    (
        "Orphan servicing NPIs (not in providers table)",
        """SELECT COUNT(DISTINCT s.servicing_npi)
           FROM spending s
           LEFT JOIN providers p ON p.npi = s.servicing_npi
           WHERE p.npi IS NULL""",
        None,
        "Servicing NPIs missing from providers table",
    ),
    # [EN] Data completeness check — providers should have practice addresses
    # [RU] Проверка полноты данных — у поставщиков должны быть адреса практики
    # [PT] Verificacao de completude dos dados — provedores devem ter enderecos de consultorio
    (
        "Providers without practice address",
        """SELECT COUNT(*)
           FROM providers p
           LEFT JOIN addresses a ON a.npi = p.npi AND a.address_purpose = 'PRACTICE'
           WHERE a.address_id IS NULL""",
        None,
        "Providers missing practice address",
    ),
    # [EN] Address parsing quality — at least 80% should have a parsed street_number
    # [RU] Качество разбора адресов — не менее 80% должны иметь разобранный street_number
    # [PT] Qualidade de analise de enderecos — pelo menos 80% devem ter street_number analisado
    (
        "Address parse rate (has street_number)",
        """SELECT
            ROUND(
                COUNT(CASE WHEN street_number IS NOT NULL THEN 1 END)::NUMERIC
                / NULLIF(COUNT(*), 0) * 100, 1
            )
           FROM addresses""",
        lambda x: x is not None and x >= 80,
        "At least 80% of addresses should have parsed street_number",
    ),
    # [EN] Geographic distribution — informational, shows top 5 states by provider count
    # [RU] Географическое распределение — информационное, показывает топ-5 штатов по числу поставщиков
    # [PT] Distribuicao geografica — informativo, mostra os 5 estados com mais provedores
    (
        "State distribution (top 5)",
        """SELECT state_code, COUNT(*) AS cnt
           FROM addresses
           WHERE address_purpose = 'PRACTICE' AND state_code IS NOT NULL
           GROUP BY state_code
           ORDER BY cnt DESC
           LIMIT 5""",
        None,
        "Top 5 states by provider count",
    ),
]


# [EN] Execute all validation queries and report results (PASS/FAIL/INFO).
#      Queries with a check function are evaluated as PASS or FAIL.
#      Queries without a check function are reported as INFO only.
#      Returns True if all threshold-based checks passed, False if any failed.
# [RU] Выполняет все валидационные запросы и выводит результаты (PASS/FAIL/INFO).
#      Запросы с функцией проверки оцениваются как PASS или FAIL.
#      Запросы без функции проверки выводятся только как INFO.
#      Возвращает True, если все пороговые проверки пройдены, False если хотя бы одна не пройдена.
# [PT] Executa todas as consultas de validacao e reporta resultados (PASS/FAIL/INFO).
#      Consultas com funcao de verificacao sao avaliadas como PASS ou FAIL.
#      Consultas sem funcao de verificacao sao reportadas apenas como INFO.
#      Retorna True se todas as verificacoes com limiar passaram, False se alguma falhou.
# Parameters / Параметры / Parametros:
#   database_url (str | None): [EN] PostgreSQL connection string | [RU] Строка подключения PostgreSQL | [PT] String de conexao PostgreSQL
# Returns / Возвращает / Retorna:
#   bool: [EN] True if all checks passed | [RU] True если все проверки пройдены | [PT] True se todas as verificacoes passaram
def run_validations(database_url: str | None = None):
    """Run all validation queries and report results."""
    database_url = database_url or os.environ["DATABASE_URL"]
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    log.info("=== Running post-load validations ===")
    passed = 0
    failed = 0
    info_only = 0

    for name, query, check, description in VALIDATION_QUERIES:
        try:
            cur.execute(query)
            result = cur.fetchall()

            # [EN] Format the result: scalar values are displayed directly, multi-row results as lists
            # [RU] Форматирование результата: скалярные значения выводятся напрямую, многострочные — как списки
            # [PT] Formata o resultado: valores escalares exibidos diretamente, resultados multi-linha como listas
            if len(result) == 1 and len(result[0]) == 1:
                value = result[0][0]
                display = str(value)
            else:
                display = str(result)
                value = result

            if check is not None:
                # [EN] Evaluate the check function against the scalar result
                # [RU] Вычисляем функцию проверки для скалярного результата
                # [PT] Avalia a funcao de verificacao contra o resultado escalar
                if check(result[0][0] if len(result) == 1 and len(result[0]) == 1 else result):
                    log.info("PASS  %-45s → %s", name, display)
                    passed += 1
                else:
                    log.warning("FAIL  %-45s → %s  (%s)", name, display, description)
                    failed += 1
            else:
                # [EN] Info-only queries — just report the value, no pass/fail judgment
                # [RU] Информационные запросы — просто выводим значение, без оценки
                # [PT] Consultas apenas informativas — apenas reporta o valor, sem julgamento
                log.info("INFO  %-45s → %s", name, display)
                info_only += 1

        except Exception as e:
            log.error("ERROR %-45s → %s", name, e)
            conn.rollback()
            failed += 1

    cur.close()
    conn.close()

    # [EN] Print validation summary: counts of passed, failed, and info-only checks
    # [RU] Вывод сводки валидации: количество пройденных, проваленных и информационных проверок
    # [PT] Imprime resumo da validacao: contagem de verificacoes aprovadas, reprovadas e informativas
    log.info("=== Validation summary ===")
    log.info("Passed: %d | Failed: %d | Info: %d", passed, failed, info_only)

    if failed > 0:
        log.warning("Some validations failed — review output above")
        return False
    return True


# [EN] Entry point: runs all validations and exits with code 0 (success) or 1 (failure)
# [RU] Точка входа: запускает все проверки и завершается с кодом 0 (успех) или 1 (неудача)
# [PT] Ponto de entrada: executa todas as validacoes e sai com codigo 0 (sucesso) ou 1 (falha)
def main():
    success = run_validations()
    # [EN] Exit code 0 = all validations passed; exit code 1 = at least one failed
    # [RU] Код выхода 0 = все проверки пройдены; код выхода 1 = хотя бы одна не пройдена
    # [PT] Codigo de saida 0 = todas validacoes passaram; codigo de saida 1 = pelo menos uma falhou
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
