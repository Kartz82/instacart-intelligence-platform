# Reproducible runner for the ingestion scripts and the dbt project.
#
# The warehouse itself is not in this image: Postgres comes from docker-compose.yml,
# and BigQuery is remote. This image only pins the Python + dbt toolchain so that a
# build on a laptop and a build in CI resolve to the same versions.
#
#   docker build -t instacart-platform .
#   docker run --rm --network host \
#     -e POSTGRES_HOST=host.docker.internal \
#     -v "$PWD:/app" instacart-platform dbt build --project-dir dbt --profiles-dir dbt

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/app/dbt

WORKDIR /app

# build-essential and libpq-dev are needed to build psycopg2 wheels on slim images.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Resolve dbt packages at build time so the image can run offline.
RUN dbt deps --project-dir dbt || true

CMD ["dbt", "build", "--project-dir", "dbt"]
