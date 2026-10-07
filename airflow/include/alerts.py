"""Failure and retry alerting shared by the Instacart DAGs.

Every alert is logged. If the Airflow Variable ``alert_webhook_url`` is set (for example
via ``AIRFLOW_VAR_ALERT_WEBHOOK_URL`` in .env), the alert is also POSTed to it as
``{"text": ...}``, the payload Slack and most chat webhooks accept.
"""

from __future__ import annotations

import json
import logging
import urllib.request

log = logging.getLogger("instacart.alerts")


def _webhook_url() -> str | None:
    try:
        from airflow.sdk import Variable

        return Variable.get("alert_webhook_url", default=None)
    except Exception:  # Variable backend unavailable: alerts still get logged
        return None


def _post(text: str) -> None:
    url = _webhook_url()
    if not url:
        return
    req = urllib.request.Request(
        url, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:  # an alert must never fail the task a second time
        log.warning("alert webhook failed: %s", exc)


def _describe(context) -> str:
    ti = context.get("task_instance") or context.get("ti")
    dag_id = getattr(ti, "dag_id", "?")
    task_id = getattr(ti, "task_id", "?")
    try_number = getattr(ti, "try_number", "?")
    run_id = context.get("run_id", "?")
    exc = context.get("exception")
    return f"{dag_id}.{task_id} run={run_id} try={try_number} error={exc!r}"


def on_failure(context) -> None:
    text = f":red_circle: Instacart pipeline FAILED — {_describe(context)}"
    log.error(text)
    _post(text)


def on_retry(context) -> None:
    log.warning("Instacart pipeline retrying — %s", _describe(context))
