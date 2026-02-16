# Расходы поставщиков медицинских услуг Medicaid — база данных и панель мониторинга

🌐 [English](README.md) | [Русский](README.ru.md) | [Portugues](README.pt.md)

Реляционная база данных и интерактивная панель мониторинга, построенные на основе [набора данных HHS о расходах поставщиков Medicaid](https://opendata.hhs.gov/datasets/medicaid-provider-spending/), дополненные данными о поставщиках из реестра NPI (NPPES).

## Возможности

- Нормализованная база данных PostgreSQL с индексированными фактами расходов, информацией о поставщиках и разобранными адресами
- ETL-конвейер для загрузки, импорта и нормализации данных HHS и NPPES
- Интерактивная панель мониторинга на Flask с графиками Plotly.js, таблицами DataTables и Bootstrap 5
- Географический анализ расходов по штатам и почтовым индексам
- Поиск поставщиков и детальные карточки с динамикой расходов
- Анализ кодов процедур HCPCS
- Развёрнуто на Render.com с автоматическим деплоем из ветки `main`

## Источники данных

- **HHS Medicaid Provider Spending** — ~200 млн строк, январь 2018 – декабрь 2024
- **NPPES NPI Registry** — имена, адреса и специализации поставщиков

## Локальная разработка

### Предварительные требования

- Python 3.11+
- PostgreSQL 15+
- Git

### Установка

```bash
git clone https://github.com/benashkar/medicaid-provider-spending.git
cd medicaid-provider-spending
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate в Windows
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env, указав URL вашей локальной базы данных
```

### Запуск ETL-конвейера

```bash
bash scripts/run_etl.sh
```

### Запуск панели мониторинга локально

```bash
flask --app app run --debug
```

## Docker

### Быстрый запуск (разработка)

```bash
docker-compose up --build
```

Эта команда поднимет панель мониторинга и базу данных PostgreSQL. Приложение будет доступно по адресу `http://localhost:10000`.

### Продакшен

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Подробнее о настройке Docker см. комментарии в файлах `Dockerfile`, `docker-compose.yml` и `docker-compose.prod.yml`.

## Развёртывание на Render

1. Создайте аккаунт на [Render](https://render.com) и подключите ваш GitHub-репозиторий
2. Используйте Blueprint (`render.yaml`) для создания базы данных и веб-сервиса
3. Заполните базу данных Render: `bash scripts/load_render_db.sh`
4. Панель мониторинга автоматически обновляется при push в ветку `main`

## Структура проекта

```
medicaid-provider-spending/
├── db/           # SQL-схема, миграции, материализованные представления
├── etl/          # Скрипты загрузки, импорта и нормализации данных
├── app/          # Приложение панели мониторинга на Flask
├── scripts/      # Shell-скрипты для настройки и ETL
└── tests/        # Набор тестов
```

## Лицензия

MIT
