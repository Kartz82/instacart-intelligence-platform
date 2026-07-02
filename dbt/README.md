# dbt Local Usage

This dbt project models the local PostgreSQL warehouse created by `src/database_loader.py`.

From the repository root:

```bash
cp .env.example .env
cp dbt/profiles.yml.example dbt/profiles.yml
export DBT_PROFILES_DIR=./dbt

dbt debug --project-dir dbt
dbt run --project-dir dbt
dbt test --project-dir dbt
```

The active warehouse target is PostgreSQL only. The raw source tables are expected in the `raw` schema.

## Layer Commands

Run staging models only:

```bash
dbt run --project-dir dbt --select path:models/staging
```

Run intermediate models only:

```bash
dbt run --project-dir dbt --select path:models/intermediate
```

Run core star schema marts only:

```bash
dbt run --project-dir dbt --select path:models/marts/core
```

Run KPI marts only:

```bash
dbt run --project-dir dbt --select path:models/marts/kpis
```

Run analysis marts only:

```bash
dbt run --project-dir dbt --select path:models/marts/analysis
```

Run all marts with upstream dependencies:

```bash
dbt run --project-dir dbt --select +path:models/marts
```

Run tests for all models:

```bash
dbt test --project-dir dbt
```

Run tests for one layer:

```bash
dbt test --project-dir dbt --select path:models/staging
dbt test --project-dir dbt --select path:models/intermediate
dbt test --project-dir dbt --select path:models/marts/core
dbt test --project-dir dbt --select path:models/marts/kpis
dbt test --project-dir dbt --select path:models/marts/analysis
```

## Analysis SQL

The SQL files in `../analysis/` query dbt marts only. Build and test the marts before running those files in PostgreSQL:

```bash
dbt run --project-dir dbt --select +path:models/marts
dbt test --project-dir dbt
```
