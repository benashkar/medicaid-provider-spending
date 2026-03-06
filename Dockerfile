# =============================================================================
# Dockerfile — Medicaid Provider Spending Dashboard
# =============================================================================
# EN: Multi-stage, production-ready Dockerfile for the Flask dashboard.
#     Stage 1 ("builder") installs build-time dependencies and compiles wheels.
#     Stage 2 ("runtime") copies only the compiled packages into a slim image,
#     runs as a non-root user, and includes a health check.
#
# RU: Многоэтапный Dockerfile для продакшен-готовой сборки панели мониторинга
#     на Flask. Этап 1 ("builder") устанавливает зависимости для сборки и
#     компилирует wheel-пакеты. Этап 2 ("runtime") копирует только
#     скомпилированные пакеты в легковесный образ, запускает приложение от
#     имени непривилегированного пользователя и включает проверку состояния.
#
# PT: Dockerfile multi-estagio pronto para producao do painel Flask.
#     Estagio 1 ("builder") instala dependencias de compilacao e gera os
#     pacotes wheel. Estagio 2 ("runtime") copia apenas os pacotes compilados
#     para uma imagem enxuta, executa como usuario sem privilegios e inclui
#     verificacao de integridade (health check).
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# EN: Install system dependencies and compile Python wheels. This stage is
#     discarded in the final image, keeping it small and free of compilers.
# RU: Установка системных зависимостей и компиляция Python wheel-пакетов.
#     Этот этап не попадает в финальный образ, сохраняя его компактным и
#     без лишних компиляторов.
# PT: Instala dependencias do sistema e compila pacotes wheel do Python.
#     Este estagio e descartado na imagem final, mantendo-a leve e sem
#     compiladores desnecessarios.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# EN: Install build-time system libraries needed to compile psycopg2 and
#     other C-extension packages. gcc and libpq-dev are required for
#     psycopg2-binary to compile from source.
# RU: Установка системных библиотек, необходимых для компиляции psycopg2
#     и других пакетов с C-расширениями. gcc и libpq-dev нужны для
#     сборки psycopg2-binary из исходного кода.
# PT: Instala bibliotecas de sistema necessarias para compilar psycopg2
#     e outros pacotes com extensoes em C. gcc e libpq-dev sao necessarios
#     para compilar o psycopg2-binary a partir do codigo-fonte.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# EN: Copy only requirements.txt first to leverage Docker layer caching.
#     If requirements.txt hasn't changed, Docker will reuse this layer.
# RU: Сначала копируем только requirements.txt для использования кэширования
#     слоёв Docker. Если requirements.txt не изменился, Docker повторно
#     использует этот слой.
# PT: Copia apenas o requirements.txt primeiro para aproveitar o cache de
#     camadas do Docker. Se o requirements.txt nao mudou, o Docker reutiliza
#     esta camada.
COPY requirements.txt .

# EN: Build wheel archives for all dependencies. These are portable binary
#     packages that can be installed without a compiler in the runtime stage.
# RU: Сборка wheel-архивов для всех зависимостей. Это переносимые бинарные
#     пакеты, которые можно установить без компилятора на этапе выполнения.
# PT: Compila arquivos wheel para todas as dependencias. Sao pacotes binarios
#     portaveis que podem ser instalados sem compilador no estagio de execucao.
RUN python -m pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2: Runtime
# EN: Minimal production image with only the compiled packages, application
#     code, and a non-root user. No compilers or build tools are present.
# RU: Минимальный продакшен-образ, содержащий только скомпилированные
#     пакеты, код приложения и непривилегированного пользователя. Без
#     компиляторов и средств сборки.
# PT: Imagem de producao minima contendo apenas os pacotes compilados,
#     codigo da aplicacao e um usuario sem privilegios. Sem compiladores
#     ou ferramentas de compilacao.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# EN: OCI labels provide metadata about the image: source repository,
#     description, license, and version. These are visible in registries
#     and via `docker inspect`.
# RU: OCI-метки содержат метаданные образа: исходный репозиторий,
#     описание, лицензия и версия. Они видны в реестрах образов и
#     через команду `docker inspect`.
# PT: Labels OCI fornecem metadados sobre a imagem: repositorio de origem,
#     descricao, licenca e versao. Sao visiveis em registros de imagens
#     e via `docker inspect`.
LABEL org.opencontainers.image.source="https://github.com/benashkar/medicaid-provider-spending"
LABEL org.opencontainers.image.description="Medicaid Provider Spending Dashboard"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="1.0.0"

WORKDIR /app

# EN: Install only the runtime system library needed for PostgreSQL
#     connections. libpq5 is the PostgreSQL client library without
#     the development headers (no -dev package needed here).
# RU: Установка только библиотеки времени выполнения, необходимой для
#     подключения к PostgreSQL. libpq5 — клиентская библиотека
#     PostgreSQL без заголовочных файлов (пакет -dev здесь не нужен).
# PT: Instala apenas a biblioteca de tempo de execucao necessaria para
#     conexoes com PostgreSQL. libpq5 e a biblioteca cliente do
#     PostgreSQL sem os headers de desenvolvimento (sem pacote -dev).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# EN: Copy pre-built wheel archives from the builder stage and install
#     them. This avoids needing gcc or any build tools in the runtime image.
# RU: Копирование собранных wheel-архивов из этапа builder и их установка.
#     Это позволяет обойтись без gcc и средств сборки в рабочем образе.
# PT: Copia os arquivos wheel pre-compilados do estagio builder e os
#     instala. Isso evita a necessidade de gcc ou ferramentas de compilacao
#     na imagem de execucao.
COPY --from=builder /build/wheels /tmp/wheels
RUN python -m pip install --no-cache-dir /tmp/wheels/* \
    && rm -rf /tmp/wheels

# EN: Copy application source code. Only the directories needed at runtime
#     are included — app/ (Flask application) and db/ (SQL schema files).
# RU: Копирование исходного кода приложения. Включены только каталоги,
#     необходимые при выполнении — app/ (приложение Flask) и db/ (SQL-схемы).
# PT: Copia o codigo-fonte da aplicacao. Apenas os diretorios necessarios
#     em tempo de execucao sao incluidos — app/ (aplicacao Flask) e db/
#     (arquivos de esquema SQL).
COPY app/ ./app/
COPY db/ ./db/

# EN: Create a non-root user "appuser" to run the application. Running as
#     root inside containers is a security risk — a compromised process
#     would have full access to the container filesystem.
# RU: Создание непривилегированного пользователя "appuser" для запуска
#     приложения. Запуск от имени root внутри контейнера — это угроза
#     безопасности: скомпрометированный процесс получит полный доступ
#     к файловой системе контейнера.
# PT: Cria um usuario sem privilegios "appuser" para executar a aplicacao.
#     Executar como root dentro de conteineres e um risco de seguranca —
#     um processo comprometido teria acesso total ao sistema de arquivos
#     do conteiner.
RUN groupadd --system appuser \
    && useradd --system --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# EN: Expose port 10000, which is the default port for Render.com deployments
#     and the port Gunicorn will listen on.
# RU: Открытие порта 10000 — порт по умолчанию для развёртывания на
#     Render.com, на котором будет слушать Gunicorn.
# PT: Expoe a porta 10000, que e a porta padrao para implantacoes no
#     Render.com e onde o Gunicorn escutara conexoes.
EXPOSE 10000

# EN: Health check — Docker will periodically call this endpoint to verify
#     the application is responsive. If it fails 3 times in a row, the
#     container is marked unhealthy and can be restarted by the orchestrator.
# RU: Проверка состояния — Docker будет периодически обращаться к этому
#     эндпоинту для проверки отзывчивости приложения. При 3 неудачных
#     попытках подряд контейнер помечается как нездоровый и может быть
#     перезапущен оркестратором.
# PT: Verificacao de integridade — o Docker chama periodicamente este
#     endpoint para verificar se a aplicacao esta respondendo. Apos 3
#     falhas consecutivas, o conteiner e marcado como nao saudavel e
#     pode ser reiniciado pelo orquestrador.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:10000/ || exit 1

# EN: Start Gunicorn with 2 workers bound to all interfaces on port 10000.
#     The app factory pattern create_app() is called to initialize Flask.
# RU: Запуск Gunicorn с 2 воркерами, привязанными ко всем интерфейсам
#     на порту 10000. Для инициализации Flask вызывается фабрика
#     приложения create_app().
# PT: Inicia o Gunicorn com 2 workers vinculados a todas as interfaces na
#     porta 10000. O padrao de fabrica create_app() e chamado para
#     inicializar o Flask.
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:10000", "--workers", "2"]
