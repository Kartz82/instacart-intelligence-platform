# Astro Runtime 3.3-8 = Apache Airflow 3.3.2 (Astronomer release notes, 2026-09-23).
FROM astrocrpublic.azurecr.io/runtime:3.3-8

# dbt lives in its own virtualenv so its dependencies can never conflict with Airflow's.
# The DAGs call it by absolute path: /usr/local/airflow/dbt_venv/bin/dbt
RUN python -m venv dbt_venv \
    && dbt_venv/bin/pip install --no-cache-dir "dbt-postgres>=1.8,<2.0"
