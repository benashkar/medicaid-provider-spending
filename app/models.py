"""
[EN] SQLAlchemy models for the Medicare Provider Spending database (read-only).
     Defines ORM models for providers, addresses, taxonomies, spending records,
     and several materialized views used for pre-aggregated analytics.
     All models map to existing PostgreSQL tables/views — no migrations needed.

[RU] Модели SQLAlchemy для базы данных расходов Medicare (только чтение).
     Определяет ORM-модели для поставщиков, адресов, таксономий, записей о расходах
     и нескольких материализованных представлений для предварительно агрегированной аналитики.
     Все модели соответствуют существующим таблицам/представлениям PostgreSQL — миграции не нужны.

[PT] Modelos SQLAlchemy para o banco de dados de gastos do Medicare (somente leitura).
     Define modelos ORM para provedores, endereços, taxonomias, registros de gastos
     e várias views materializadas usadas para análises pré-agregadas.
     Todos os modelos mapeiam tabelas/views PostgreSQL existentes — sem necessidade de migrações.
"""

from flask_sqlalchemy import SQLAlchemy

# [EN] Create the SQLAlchemy database instance. It is initialized with the Flask app in __init__.py.
# [RU] Создать экземпляр базы данных SQLAlchemy. Инициализируется с приложением Flask в __init__.py.
# [PT] Criar a instância do banco de dados SQLAlchemy. É inicializada com o app Flask em __init__.py.
db = SQLAlchemy()


# =============================================================================
# [EN] CORE TABLES — Primary data tables storing provider and spending records
# [RU] ОСНОВНЫЕ ТАБЛИЦЫ — Первичные таблицы с данными поставщиков и расходов
# [PT] TABELAS PRINCIPAIS — Tabelas primárias com dados de provedores e gastos
# =============================================================================


# [EN] Provider model — represents a healthcare provider (individual or organization).
#      entity_type=1 means individual, entity_type=2 means organization.
#      The NPI (National Provider Identifier) is a unique 10-digit number.
# [RU] Модель поставщика — представляет медицинского поставщика (физическое лицо или организацию).
#      entity_type=1 — физическое лицо, entity_type=2 — организация.
#      NPI (Национальный идентификатор поставщика) — уникальный 10-значный номер.
# [PT] Modelo de provedor — representa um provedor de saúde (pessoa física ou organização).
#      entity_type=1 significa pessoa física, entity_type=2 significa organização.
#      O NPI (Identificador Nacional de Provedor) é um número único de 10 dígitos.
class Provider(db.Model):
    __tablename__ = "providers"

    npi = db.Column(db.String(10), primary_key=True)
    entity_type = db.Column(db.SmallInteger, nullable=False)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    middle_name = db.Column(db.Text)
    credential = db.Column(db.Text)
    is_sole_proprietor = db.Column(db.Boolean)
    is_org_subpart = db.Column(db.Boolean)
    parent_org_name = db.Column(db.Text)
    parent_org_tin = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_phone = db.Column(db.Text)
    enumeration_date = db.Column(db.Date)
    last_update_date = db.Column(db.Date)
    deactivation_date = db.Column(db.Date)
    reactivation_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True))

    # [EN] Relationships to related tables — lazy="select" means they are loaded on first access
    # [RU] Связи с родственными таблицами — lazy="select" означает загрузку при первом обращении
    # [PT] Relacionamentos com tabelas relacionadas — lazy="select" significa carregamento no primeiro acesso
    addresses = db.relationship("Address", backref="provider", lazy="select")
    taxonomies = db.relationship("ProviderTaxonomy", backref="provider", lazy="select")

    # [EN] Returns a human-readable name: organization name for orgs, "First Last, Credential" for individuals.
    #      Falls back to the NPI number if no name is available.
    # [RU] Возвращает читаемое имя: название организации для организаций, «Имя Фамилия, Квалификация» для физических лиц.
    #      Если имя отсутствует, возвращает номер NPI.
    # [PT] Retorna um nome legível: nome da organização para organizações, "Nome Sobrenome, Credencial" para pessoas físicas.
    #      Retorna o número NPI se nenhum nome estiver disponível.
    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p)
        if self.credential:
            name += f", {self.credential}"
        return name or self.npi


# [EN] Address model — stores mailing and practice addresses for providers.
#      Each provider can have multiple addresses (e.g., mailing vs. practice location).
# [RU] Модель адреса — хранит почтовые и практические адреса поставщиков.
#      У каждого поставщика может быть несколько адресов (например, почтовый и адрес практики).
# [PT] Modelo de endereço — armazena endereços de correspondência e consultório dos provedores.
#      Cada provedor pode ter múltiplos endereços (ex.: correspondência vs. local de atendimento).
class Address(db.Model):
    __tablename__ = "addresses"

    address_id = db.Column(db.Integer, primary_key=True)
    npi = db.Column(db.String(10), db.ForeignKey("providers.npi"), nullable=False)
    address_purpose = db.Column(db.Text, nullable=False)
    street_line_1 = db.Column(db.Text)
    street_line_2 = db.Column(db.Text)
    city = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    zip5 = db.Column(db.String(5))
    zip4 = db.Column(db.String(4))
    country_code = db.Column(db.String(2))
    phone = db.Column(db.Text)
    fax = db.Column(db.Text)
    # [EN] Parsed/normalized address components (populated by ETL pipeline)
    # [RU] Разобранные/нормализованные компоненты адреса (заполняются ETL-конвейером)
    # [PT] Componentes de endereço analisados/normalizados (preenchidos pelo pipeline ETL)
    street_number = db.Column(db.Text)
    street_name = db.Column(db.Text)
    street_suffix = db.Column(db.Text)
    unit_type = db.Column(db.Text)
    unit_number = db.Column(db.Text)

    # [EN] Builds a formatted full address string from individual components (e.g., "123 Main St, Boston, MA, 02101")
    # [RU] Формирует полную строку адреса из отдельных компонентов (например, «123 Main St, Boston, MA, 02101»)
    # [PT] Constrói uma string de endereço completo a partir dos componentes individuais (ex.: "123 Main St, Boston, MA, 02101")
    @property
    def full_address(self):
        parts = [self.street_line_1]
        if self.street_line_2:
            parts.append(self.street_line_2)
        # [EN] Combine city and state with comma separator, skipping None values
        # [RU] Объединить город и штат через запятую, пропуская пустые значения
        # [PT] Combinar cidade e estado com separador de vírgula, ignorando valores nulos
        city_state = ", ".join(p for p in [self.city, self.state_code] if p)
        if city_state:
            parts.append(city_state)
        if self.zip5:
            parts.append(self.zip5)
        return ", ".join(parts)


# [EN] Provider taxonomy — links providers to their healthcare specialty codes.
#      A provider can have multiple taxonomies; one is marked as primary.
# [RU] Таксономия поставщика — связывает поставщиков с кодами медицинских специальностей.
#      У поставщика может быть несколько таксономий; одна помечена как основная.
# [PT] Taxonomia do provedor — vincula provedores aos seus códigos de especialidade médica.
#      Um provedor pode ter múltiplas taxonomias; uma é marcada como principal.
class ProviderTaxonomy(db.Model):
    __tablename__ = "provider_taxonomies"

    id = db.Column(db.Integer, primary_key=True)
    npi = db.Column(db.String(10), db.ForeignKey("providers.npi"), nullable=False)
    taxonomy_code = db.Column(db.Text, nullable=False)
    license_number = db.Column(db.Text)
    license_state = db.Column(db.String(2))
    is_primary = db.Column(db.Boolean, default=False)


# [EN] Taxonomy code reference — NUCC Health Care Provider Taxonomy Code Set.
#      Maps 10-character taxonomy codes to human-readable descriptions, groupings, and classifications.
# [RU] Справочная таблица таксономий — Набор таксономических кодов NUCC.
#      Сопоставляет 10-символьные коды таксономий с читаемыми описаниями, группами и классификациями.
# [PT] Referência de códigos de taxonomia — Conjunto de Códigos de Taxonomia NUCC.
#      Mapeia códigos de taxonomia de 10 caracteres para descrições legíveis, agrupamentos e classificações.
class TaxonomyCode(db.Model):
    __tablename__ = "taxonomy_codes"

    taxonomy_code = db.Column(db.Text, primary_key=True)
    grouping = db.Column(db.Text)
    classification = db.Column(db.Text)
    specialization = db.Column(db.Text)
    display_name = db.Column(db.Text)
    definition = db.Column(db.Text)
    section = db.Column(db.Text)


# [EN] HCPCS code reference table — Healthcare Common Procedure Coding System.
#      Maps procedure codes to human-readable descriptions and categories.
# [RU] Справочная таблица кодов HCPCS — Система кодирования медицинских процедур.
#      Сопоставляет коды процедур с читаемыми описаниями и категориями.
# [PT] Tabela de referência de códigos HCPCS — Sistema de Codificação de Procedimentos Médicos.
#      Mapeia códigos de procedimentos para descrições legíveis e categorias.
class HcpcsCode(db.Model):
    __tablename__ = "hcpcs_codes"

    hcpcs_code = db.Column(db.Text, primary_key=True)
    short_description = db.Column(db.Text)
    long_description = db.Column(db.Text)
    category = db.Column(db.Text)


# [EN] Spending record — one row per provider+procedure+month combination.
#      Contains claim counts, payment amounts, and beneficiary counts.
# [RU] Запись о расходах — одна строка на комбинацию поставщик+процедура+месяц.
#      Содержит количество заявок, суммы выплат и количество получателей услуг.
# [PT] Registro de gastos — uma linha por combinação provedor+procedimento+mês.
#      Contém contagens de sinistros, valores de pagamento e contagens de beneficiários.
class Spending(db.Model):
    __tablename__ = "spending"

    id = db.Column(db.BigInteger, primary_key=True)
    billing_npi = db.Column(db.String(10), nullable=False)
    servicing_npi = db.Column(db.String(10), nullable=False)
    hcpcs_code = db.Column(db.Text, nullable=False)
    claim_month = db.Column(db.Date, nullable=False)
    total_unique_benes = db.Column(db.Integer)
    total_claims = db.Column(db.Integer)
    total_paid = db.Column(db.Numeric(15, 2))


# =============================================================================
# [EN] MATERIALIZED VIEWS — Pre-aggregated data for fast dashboard queries.
#      These are read-only and refreshed periodically by the database.
# [RU] МАТЕРИАЛИЗОВАННЫЕ ПРЕДСТАВЛЕНИЯ — Предварительно агрегированные данные
#      для быстрых запросов к панели. Только для чтения, обновляются периодически базой данных.
# [PT] VIEWS MATERIALIZADAS — Dados pré-agregados para consultas rápidas no painel.
#      Somente leitura, atualizadas periodicamente pelo banco de dados.
# =============================================================================


# [EN] Provider spending summary — one row per billing provider with lifetime totals.
#      Used for the provider rankings/search page.
# [RU] Сводка расходов поставщика — одна строка на поставщика с итогами за всё время.
#      Используется для страницы рейтинга/поиска поставщиков.
# [PT] Resumo de gastos por provedor — uma linha por provedor com totais acumulados.
#      Usado para a página de classificação/busca de provedores.
class MvProviderSpendingSummary(db.Model):
    __tablename__ = "mv_provider_spending_summary"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    entity_type = db.Column(db.SmallInteger)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    zip5 = db.Column(db.String(5))
    total_rows = db.Column(db.BigInteger)
    lifetime_claims = db.Column(db.BigInteger)
    lifetime_paid = db.Column(db.Numeric)
    lifetime_benes = db.Column(db.BigInteger)
    first_claim_month = db.Column(db.Date)
    last_claim_month = db.Column(db.Date)
    distinct_hcpcs_codes = db.Column(db.BigInteger)

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.billing_npi


# [EN] Monthly spending totals — one row per month with aggregate counts.
#      Powers the spending trends chart on the dashboard.
# [RU] Ежемесячные итоги расходов — одна строка на месяц с агрегированными показателями.
#      Используется для графика трендов расходов на панели.
# [PT] Totais mensais de gastos — uma linha por mês com contagens agregadas.
#      Alimenta o gráfico de tendências de gastos no painel.
class MvMonthlySpending(db.Model):
    __tablename__ = "mv_monthly_spending"
    __table_args__ = {"info": {"is_view": True}}

    claim_month = db.Column(db.Date, primary_key=True)
    active_providers = db.Column(db.BigInteger)
    total_claims = db.Column(db.BigInteger)
    total_paid = db.Column(db.Numeric)
    total_benes = db.Column(db.BigInteger)


# [EN] State-level spending summary — one row per US state with totals.
#      Used for the geographic spending breakdown page.
# [RU] Сводка расходов по штатам — одна строка на штат США с итогами.
#      Используется для страницы географического распределения расходов.
# [PT] Resumo de gastos por estado — uma linha por estado dos EUA com totais.
#      Usado para a página de distribuição geográfica de gastos.
class MvStateSpending(db.Model):
    __tablename__ = "mv_state_spending"
    __table_args__ = {"info": {"is_view": True}}

    state_code = db.Column(db.String(2), primary_key=True)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    provider_count = db.Column(db.BigInteger)
    total_benes = db.Column(db.BigInteger)


# [EN] HCPCS code spending summary — one row per procedure code with totals.
#      Shows which medical procedures have the highest Medicare spending.
# [RU] Сводка расходов по кодам HCPCS — одна строка на код процедуры с итогами.
#      Показывает, на какие медицинские процедуры приходятся наибольшие расходы Medicare.
# [PT] Resumo de gastos por código HCPCS — uma linha por código de procedimento com totais.
#      Mostra quais procedimentos médicos têm os maiores gastos do Medicare.
class MvHcpcsSpending(db.Model):
    __tablename__ = "mv_hcpcs_spending"
    __table_args__ = {"info": {"is_view": True}}

    hcpcs_code = db.Column(db.Text, primary_key=True)
    short_description = db.Column(db.Text)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    provider_count = db.Column(db.BigInteger)


# =============================================================================
# [EN] ANALYSIS VIEWS — Advanced analytical views for deeper spending analysis
# [RU] АНАЛИТИЧЕСКИЕ ПРЕДСТАВЛЕНИЯ — Расширенные аналитические представления
#      для углублённого анализа расходов
# [PT] VIEWS DE ANÁLISE — Views analíticas avançadas para análise aprofundada de gastos
# =============================================================================


# [EN] Top organizations by lifetime spending — ranks the highest-spending organizations.
#      Includes location, claim period, and number of distinct procedures.
# [RU] Топ-организации по расходам за всё время — ранжирует организации с наибольшими расходами.
#      Включает местоположение, период заявок и количество различных процедур.
# [PT] Principais organizações por gastos acumulados — classifica as organizações com maiores gastos.
#      Inclui localização, período de sinistros e número de procedimentos distintos.
class MvTopOrganizations(db.Model):
    __tablename__ = "mv_top_organizations"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    entity_type = db.Column(db.SmallInteger)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    lifetime_paid = db.Column(db.Numeric)
    lifetime_claims = db.Column(db.BigInteger)
    lifetime_benes = db.Column(db.BigInteger)
    distinct_hcpcs = db.Column(db.BigInteger)
    first_claim = db.Column(db.Date)
    last_claim = db.Column(db.Date)


# [EN] Spending growth — year-over-year payment changes per provider (individuals & orgs).
#      Shows annual spending, previous year spending, dollar change, and percentage change.
#      Filterable by year range and minimum % growth at the application level.
# [RU] Рост расходов — годовые изменения выплат по каждому поставщику (физ. лица и организации).
#      Показывает годовые расходы, расходы предыдущего года, изменение в долларах и процентах.
# [PT] Crescimento de gastos — mudanças anuais de pagamento por provedor (individuais e organizações).
#      Mostra gastos anuais, gastos do ano anterior, variação em dólares e percentual.
class MvSpendingGrowth(db.Model):
    __tablename__ = "mv_spending_growth"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    entity_type = db.Column(db.SmallInteger)
    authorized_official_first = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    claim_year = db.Column(db.Integer, primary_key=True)
    prev_year = db.Column(db.Integer)
    annual_paid = db.Column(db.Numeric)
    prev_year_paid = db.Column(db.Numeric)
    dollar_change = db.Column(db.Numeric)
    pct_change = db.Column(db.Numeric)
    annual_claims = db.Column(db.Integer)
    prev_year_claims = db.Column(db.Integer)
    annual_benes = db.Column(db.Integer)

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.billing_npi


# [EN] Outlier providers — providers whose spending on a given HCPCS code is more than
#      2 standard deviations above the peer group mean (statistical anomaly detection).
# [RU] Аномальные поставщики — поставщики, чьи расходы по данному коду HCPCS превышают
#      среднее по группе более чем на 2 стандартных отклонения (статистическое обнаружение аномалий).
# [PT] Provedores atípicos — provedores cujos gastos em um dado código HCPCS excedem
#      a média do grupo em mais de 2 desvios padrão (detecção estatística de anomalias).
class MvOutlierProviders(db.Model):
    __tablename__ = "mv_outlier_providers"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    entity_type = db.Column(db.SmallInteger)
    hcpcs_code = db.Column(db.Text, primary_key=True)
    short_description = db.Column(db.Text)
    provider_paid = db.Column(db.Numeric)
    # [EN] Average spending among all providers for the same HCPCS code
    # [RU] Средние расходы среди всех поставщиков по тому же коду HCPCS
    # [PT] Gasto médio entre todos os provedores para o mesmo código HCPCS
    peer_mean = db.Column(db.Numeric)
    # [EN] Standard deviation of spending among peers — measures how spread out the values are
    # [RU] Стандартное отклонение расходов среди коллег — измеряет разброс значений
    # [PT] Desvio padrão dos gastos entre pares — mede a dispersão dos valores
    peer_stddev = db.Column(db.Numeric)
    # [EN] Z-score = (provider_paid - peer_mean) / peer_stddev. Higher z-score = more anomalous.
    # [RU] Z-оценка = (расходы_поставщика - среднее) / стд_отклонение. Чем выше — тем аномальнее.
    # [PT] Z-score = (gasto_provedor - média) / desvio_padrão. Maior z-score = mais anômalo.
    z_score = db.Column(db.Numeric)
    peer_count = db.Column(db.BigInteger)

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.billing_npi


# [EN] Geographic concentration — spending aggregated by state + ZIP code.
#      Shows which areas have the highest Medicare spending density.
# [RU] Географическая концентрация — расходы, агрегированные по штату и почтовому индексу.
#      Показывает, какие районы имеют наибольшую плотность расходов Medicare.
# [PT] Concentração geográfica — gastos agregados por estado e código postal.
#      Mostra quais áreas possuem a maior densidade de gastos do Medicare.
class MvGeographicConcentration(db.Model):
    __tablename__ = "mv_geographic_concentration"
    __table_args__ = {"info": {"is_view": True}}

    state_code = db.Column(db.String(2), primary_key=True)
    zip5 = db.Column(db.String(5), primary_key=True)
    city = db.Column(db.Text)
    provider_count = db.Column(db.BigInteger)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    total_benes = db.Column(db.BigInteger)
    avg_paid_per_provider = db.Column(db.Numeric)


# [EN] Billing-servicing network — relationships between billing and servicing providers.
#      Shows which organizations bill on behalf of which servicing providers and the total volume.
# [RU] Сеть биллинг-обслуживание — связи между выставляющими счета и обслуживающими поставщиками.
#      Показывает, какие организации выставляют счета от имени каких поставщиков и общий объём.
# [PT] Rede de faturamento-atendimento — relacionamentos entre provedores faturadores e atendentes.
#      Mostra quais organizações faturam em nome de quais provedores de atendimento e o volume total.
class MvBillingServicingNetwork(db.Model):
    __tablename__ = "mv_billing_servicing_network"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    billing_org = db.Column(db.Text)
    billing_last = db.Column(db.Text)
    billing_type = db.Column(db.SmallInteger)
    servicing_npi = db.Column(db.String(10), primary_key=True)
    servicing_org = db.Column(db.Text)
    servicing_last = db.Column(db.Text)
    servicing_type = db.Column(db.SmallInteger)
    total_paid = db.Column(db.Numeric)
    total_claims = db.Column(db.BigInteger)
    shared_hcpcs = db.Column(db.BigInteger)
    first_month = db.Column(db.Date)
    last_month = db.Column(db.Date)


# =============================================================================
# [EN] FRAUD DETECTION VIEWS — Advanced views for identifying potential fraud patterns
# [RU] ПРЕДСТАВЛЕНИЯ ДЛЯ ОБНАРУЖЕНИЯ МОШЕННИЧЕСТВА — Расширенные представления
#      для выявления потенциальных схем мошенничества
# [PT] VIEWS DE DETECÇÃO DE FRAUDE — Views avançadas para identificar padrões
#      potenciais de fraude
# =============================================================================


# [EN] Year-over-Year organization spending growth — compares annual totals across
#      consecutive years. Shows raw dollar increase and percentage change.
#      Focused on organizations (entity_type=2) for fraud pattern detection.
# [RU] Годовой рост расходов организаций — сравнивает годовые итоги за
#      последовательные годы. Показывает рост в долларах и процентах.
#      Только организации (entity_type=2) для обнаружения мошенничества.
# [PT] Crescimento anual de gastos por organização — compara totais anuais entre
#      anos consecutivos. Mostra aumento em dólares e percentual.
#      Focado em organizações (entity_type=2) para detecção de fraude.
class MvOrgYoyGrowth(db.Model):
    __tablename__ = "mv_org_yoy_growth"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    claim_year = db.Column(db.Integer, primary_key=True)
    prev_year = db.Column(db.Integer)
    annual_paid = db.Column(db.Numeric)
    prev_year_paid = db.Column(db.Numeric)
    dollar_increase = db.Column(db.Numeric)
    pct_increase = db.Column(db.Numeric)
    annual_claims = db.Column(db.BigInteger)
    prev_year_claims = db.Column(db.BigInteger)
    annual_benes = db.Column(db.BigInteger)
    distinct_hcpcs = db.Column(db.BigInteger)


# [EN] Address clustering — groups providers sharing the same building location
#      (street_number + street_name + zip5). Multiple providers at the same building
#      with different unit numbers is a common fraud indicator.
# [RU] Кластеризация адресов — группирует поставщиков по одному зданию
#      (номер дома + название улицы + индекс). Несколько поставщиков в одном здании
#      с разными номерами офисов — распространённый индикатор мошенничества.
# [PT] Clustering de endereços — agrupa provedores no mesmo edifício
#      (número + nome da rua + CEP). Múltiplos provedores no mesmo edifício
#      com diferentes números de unidade é um indicador comum de fraude.
class MvAddressClustering(db.Model):
    __tablename__ = "mv_address_clustering"
    __table_args__ = {"info": {"is_view": True}}

    building_number = db.Column(db.Text, primary_key=True)
    building_street = db.Column(db.Text, primary_key=True)
    zip5 = db.Column(db.String(5), primary_key=True)
    city = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    provider_count = db.Column(db.BigInteger)
    distinct_units = db.Column(db.BigInteger)
    combined_spending = db.Column(db.Numeric)
    combined_claims = db.Column(db.BigInteger)
    npis = db.Column(db.JSON)
    unit_numbers = db.Column(db.JSON)
    org_names = db.Column(db.JSON)


# [EN] Rapid ramp detection — organizations registered since 2020 that quickly reached
#      high spending levels. Shows days from NPI enumeration to first claim and average
#      monthly spend rate. New org → fast high spending = suspicious pattern.
# [RU] Обнаружение быстрого роста — организации, зарегистрированные с 2020 года,
#      которые быстро достигли высоких уровней расходов. Показывает дни от регистрации NPI
#      до первого заявления и средний месячный расход. Новая организация → быстрые высокие расходы = подозрительно.
# [PT] Detecção de rampa rápida — organizações registradas desde 2020 que rapidamente
#      atingiram altos níveis de gastos. Mostra dias da enumeração NPI até o primeiro
#      sinistro e gasto mensal médio. Nova org → gastos altos rápidos = padrão suspeito.
class MvRapidRamp(db.Model):
    __tablename__ = "mv_rapid_ramp"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    enumeration_date = db.Column(db.Date)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    first_claim_month = db.Column(db.Date)
    last_claim_month = db.Column(db.Date)
    lifetime_paid = db.Column(db.Numeric)
    lifetime_claims = db.Column(db.BigInteger)
    active_months = db.Column(db.BigInteger)
    avg_monthly_spend = db.Column(db.Numeric)
    days_to_first_claim = db.Column(db.Integer)


# [EN] Composite fraud risk score — combines 5 fraud signals per organization:
#      1) YoY spending spike, 2) Statistical outlier codes, 3) Month-over-month spikes,
#      4) Shared address clustering, 5) Complex billing network.
#      Risk score 0-5 = number of flags triggered. Higher = more suspicious.
# [RU] Комплексная оценка риска мошенничества — объединяет 5 сигналов на организацию:
#      1) Скачок YoY, 2) Статистически аномальные коды, 3) Ежемесячные скачки,
#      4) Кластеризация адресов, 5) Сложная биллинговая сеть.
#      Балл риска 0-5 = количество сработавших флагов. Выше = подозрительнее.
# [PT] Pontuação composta de risco de fraude — combina 5 sinais por organização:
#      1) Pico YoY, 2) Códigos outlier, 3) Picos mensais,
#      4) Clustering de endereço, 5) Rede complexa de faturamento.
#      Score 0-5 = número de indicadores ativados. Maior = mais suspeito.
class MvFraudRiskScore(db.Model):
    __tablename__ = "mv_fraud_risk_score"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    organization_name = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    lifetime_paid = db.Column(db.Numeric)
    lifetime_claims = db.Column(db.BigInteger)
    first_claim = db.Column(db.Date)
    last_claim = db.Column(db.Date)
    # Individual flags (0 or 1)
    flag_yoy_spike = db.Column(db.Integer)
    max_yoy_dollar = db.Column(db.Numeric)
    max_yoy_pct = db.Column(db.Numeric)
    flag_outlier = db.Column(db.Integer)
    outlier_code_count = db.Column(db.BigInteger)
    max_z_score = db.Column(db.Numeric)
    flag_mom_spike = db.Column(db.Integer)
    spike_count = db.Column(db.BigInteger)
    max_spike_pct = db.Column(db.Numeric)
    flag_shared_address = db.Column(db.Integer)
    building_provider_count = db.Column(db.BigInteger)
    flag_network_complexity = db.Column(db.Integer)
    servicing_partner_count = db.Column(db.BigInteger)
    # Composite score (0-5)
    risk_score = db.Column(db.Integer)


# [EN] Average claim amount by provider — shows the avg payment per claim for each
#      provider with location. Useful for identifying unusually high or low claim values.
# [RU] Средняя сумма заявки по поставщику — показывает среднюю выплату за заявку
#      для каждого поставщика с местоположением. Полезно для выявления необычных сумм.
# [PT] Valor médio de sinistro por provedor — mostra o pagamento médio por sinistro
#      para cada provedor com localização. Útil para identificar valores incomuns.
class MvAvgClaimByProvider(db.Model):
    __tablename__ = "mv_avg_claim_by_provider"
    __table_args__ = {"info": {"is_view": True}}

    billing_npi = db.Column(db.String(10), primary_key=True)
    entity_type = db.Column(db.SmallInteger)
    organization_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    first_name = db.Column(db.Text)
    authorized_official_first = db.Column(db.Text)
    authorized_official_last = db.Column(db.Text)
    state_code = db.Column(db.String(2))
    city = db.Column(db.Text)
    zip5 = db.Column(db.String(5))
    lifetime_paid = db.Column(db.Numeric)
    lifetime_claims = db.Column(db.BigInteger)
    lifetime_benes = db.Column(db.BigInteger)
    avg_claim_amount = db.Column(db.Numeric)
    distinct_hcpcs = db.Column(db.BigInteger)
    first_claim = db.Column(db.Date)
    last_claim = db.Column(db.Date)

    @property
    def display_name(self):
        if self.entity_type == 2 and self.organization_name:
            return self.organization_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.billing_npi


# [EN] Authorized official network — groups organizations by the person listed as their
#      authorized official. Flags individuals controlling 2+ Medicaid-billing organizations.
#      One person running 5+ companies billing Medicaid is a major fraud indicator.
# [RU] Сеть уполномоченных лиц — группирует организации по лицу, указанному как
#      уполномоченное. Помечает лиц, контролирующих 2+ организации, выставляющие счета Medicaid.
# [PT] Rede de oficiais autorizados — agrupa organizações pela pessoa listada como
#      oficial autorizado. Identifica indivíduos controlando 2+ organizações do Medicaid.
class MvOfficialNetwork(db.Model):
    __tablename__ = "mv_official_network"
    __table_args__ = {"info": {"is_view": True}}

    official_last = db.Column(db.Text, primary_key=True)
    official_first = db.Column(db.Text, primary_key=True)
    org_count = db.Column(db.BigInteger)
    combined_spending = db.Column(db.Numeric)
    combined_claims = db.Column(db.BigInteger)
    npis = db.Column(db.JSON)
    org_names = db.Column(db.JSON)
    states = db.Column(db.JSON)
    cities = db.Column(db.JSON)
    state_count = db.Column(db.BigInteger)
