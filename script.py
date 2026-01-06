import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

log = logging.getLogger("client")


@dataclass(frozen=True)
class Settings:
    api: str = "http://127.0.0.1:8010"
    timeout: int = 30
    poll_seconds: float = 2.0
    max_polls: int = 300  # 300 * 2s = 10 min


PAYLOAD: Dict[str, Any] = {
    "project_name": "Teste",
    "dataset_path": r"D:/Judson_projetos/cvat-flow/datasets/images",
    "task_size": 100,
    "img_quality": 85,
    "chunk_size": 100,
}


def create_job(session: requests.Session, cfg: Settings, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = session.post(f"{cfg.api}/upload", json=payload, timeout=cfg.timeout)
    resp.raise_for_status()
    return resp.json()


def get_job_status(session: requests.Session, cfg: Settings, job_id: str) -> Dict[str, Any]:
    resp = session.get(f"{cfg.api}/jobs/{job_id}", timeout=cfg.timeout)
    resp.raise_for_status()
    return resp.json()


def poll_until_done(session: requests.Session, cfg: Settings, job_id: str) -> Dict[str, Any]:
    for i in range(1, cfg.max_polls + 1):
        status_data = get_job_status(session, cfg, job_id)
        status = status_data.get("status")
        detail = status_data.get("detail")

        log.info("poll=%d/%d job_id=%s status=%s detail=%s", i, cfg.max_polls, job_id, status, detail)

        if status == "done":
            return status_data
        if status == "error":
            raise RuntimeError(f"Job error: {detail or status_data}")

        time.sleep(cfg.poll_seconds)

    raise TimeoutError(f"Job {job_id} did not finish after {cfg.max_polls} polls")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    cfg = Settings()

    try:
        with requests.Session() as session:
            job = create_job(session, cfg, PAYLOAD)
            job_id = job["job_id"]
            log.info("Job criado: %s | status=%s", job_id, job.get("status"))

            final_status = poll_until_done(session, cfg, job_id)
            log.info("Final: status=%s task_ids=%s", final_status.get("status"), final_status.get("task_ids"))
            return 0

    except requests.exceptions.RequestException as e:
        # erro de rede / HTTP
        log.exception("Falha HTTP/requests: %s", e)
        return 2
    except Exception as e:
        log.exception("Erro geral: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
