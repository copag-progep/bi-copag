#!/usr/bin/env python3
"""
Verifica se o upload diário do SEI concluiu com sucesso hoje.

Usado pela recuperação do upload e pelo relatório diário. A recuperação evita
coleta duplicada quando a execução principal funcionou; o relatório evita envio
de indicadores desatualizados quando nenhuma tentativa teve sucesso.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_VERSION = "2022-11-28"
DEFAULT_WORKFLOW_FILE = "daily-upload.yml"
TIMEZONE = ZoneInfo("America/Fortaleza")


def _github_output(**values: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fetch_runs(repo: str, workflow_file: str, token: str) -> list[dict[str, Any]]:
    workflow_id = quote(workflow_file, safe="")
    runs: list[dict[str, Any]] = []
    for page in range(1, 4):
        url = (
            f"https://api.github.com/repos/{repo}/actions/workflows/"
            f"{workflow_id}/runs?status=completed&per_page=30&page={page}"
        )
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "analyticsei-daily-report-gate",
            },
        )
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        page_runs = payload.get("workflow_runs", [])
        runs.extend(page_runs)
        if len(page_runs) < 30:
            break
    return runs


def main() -> int:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    workflow_file = os.getenv("UPLOAD_WORKFLOW_FILE", DEFAULT_WORKFLOW_FILE)

    if not token or not repo:
        print("Não foi possível verificar o upload: GITHUB_TOKEN/GITHUB_REPOSITORY ausente.")
        _github_output(upload_ok="false", reason="missing_github_context")
        return 1

    today = datetime.now(TIMEZONE).date()
    runs = _fetch_runs(repo, workflow_file, token)

    print(f"Verificando workflow {workflow_file} para a data {today.isoformat()}...")

    for run in runs:
        started = _parse_dt(run.get("run_started_at") or run.get("created_at"))
        if not started:
            continue
        local_date = started.astimezone(TIMEZONE).date()
        if local_date != today:
            continue
        if run.get("conclusion") == "success":
            run_id = str(run.get("id", ""))
            run_url = run.get("html_url", "")
            run_time = started.astimezone(TIMEZONE).isoformat(timespec="seconds")
            print(f"Upload diário encontrado com sucesso: {run_url}")
            _github_output(
                upload_ok="true",
                upload_run_id=run_id,
                upload_run_url=run_url,
                upload_run_time=run_time,
            )
            return 0

        print(
            "Execução encontrada hoje, mas sem sucesso: "
            f"id={run.get('id')} conclusion={run.get('conclusion')} url={run.get('html_url')}"
        )

    print("Nenhum upload diário bem-sucedido encontrado hoje.")
    _github_output(upload_ok="false", reason="no_successful_upload_today")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Falha ao verificar upload diário: {type(exc).__name__}: {exc}")
        _github_output(upload_ok="false", reason="check_failed")
        raise
