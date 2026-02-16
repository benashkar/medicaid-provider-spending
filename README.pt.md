# Gastos de Provedores Medicaid — Banco de Dados e Painel

🌐 [English](README.md) | [Русский](README.ru.md) | [Portugues](README.pt.md)

Banco de dados relacional e painel interativo construidos a partir do [conjunto de dados de gastos de provedores Medicaid do HHS](https://opendata.hhs.gov/datasets/medicaid-provider-spending/), enriquecidos com dados de provedores do registro NPI (NPPES).

## Funcionalidades

- Banco de dados PostgreSQL normalizado com fatos de gastos indexados, detalhes de provedores e enderecos analisados
- Pipeline ETL para download, carregamento e normalizacao de dados do HHS e NPPES
- Painel interativo em Flask com graficos Plotly.js, DataTables e Bootstrap 5
- Analise geografica de gastos por estado e CEP
- Busca de provedores e visualizacao detalhada com tendencias de gastos
- Analise de codigos de procedimentos HCPCS
- Implantado no Render.com com deploy automatico a partir da branch `main`

## Fontes de Dados

- **HHS Medicaid Provider Spending** — ~200 milhoes de linhas, janeiro de 2018 a dezembro de 2024
- **NPPES NPI Registry** — nomes, enderecos e especialidades dos provedores

## Desenvolvimento Local

### Pre-requisitos

- Python 3.11+
- PostgreSQL 15+
- Git

### Configuracao

```bash
git clone https://github.com/benashkar/medicaid-provider-spending.git
cd medicaid-provider-spending
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
cp .env.example .env
# Edite o .env com a URL do seu banco de dados local
```

### Executar o Pipeline ETL

```bash
bash scripts/run_etl.sh
```

### Executar o Painel Localmente

```bash
flask --app app run --debug
```

## Docker

### Inicio Rapido (desenvolvimento)

```bash
docker-compose up --build
```

Este comando inicia o painel e o banco de dados PostgreSQL. A aplicacao estara disponivel em `http://localhost:10000`.

### Producao

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Para mais detalhes sobre a configuracao Docker, consulte os comentarios nos arquivos `Dockerfile`, `docker-compose.yml` e `docker-compose.prod.yml`.

## Implantacao no Render

1. Crie uma conta no [Render](https://render.com) e conecte seu repositorio GitHub
2. Use o Blueprint (`render.yaml`) para provisionar o banco de dados e o servico web
3. Popule o banco de dados do Render: `bash scripts/load_render_db.sh`
4. O painel e atualizado automaticamente a cada push na branch `main`

## Estrutura do Projeto

```
medicaid-provider-spending/
├── db/           # Esquema SQL, migracoes, views materializadas
├── etl/          # Scripts de download, carregamento e normalizacao de dados
├── app/          # Aplicacao do painel em Flask
├── scripts/      # Scripts shell para configuracao e ETL
└── tests/        # Suite de testes
```

## Licenca

MIT
