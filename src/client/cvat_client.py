# src/utils/cvat_client.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cvat_sdk.api_client import ApiClient, Configuration, models, exceptions


@dataclass
class CvatClient:
    """
    Wrapper em cima do cvat-sdk, focado em:
      - about()
      - (get|get_or_create)_project
      - create_task()
      - attach_data_to_task() usando TUS
    """
    base_url: str
    token: str
    organization: Optional[str] = None
    timeout: int = 60

    api_client: ApiClient = field(init=False)
    _org_kwargs: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        # Autenticação: CVAT esperando Authorization: Token <token>
        cfg = Configuration(host=self.base_url)
        cfg.api_key["tokenAuth"] = self.token
        cfg.api_key_prefix["tokenAuth"] = "Token"

        self.api_client = ApiClient(cfg)

        # kwargs padrão de organização para os endpoints que aceitam "org"
        self._org_kwargs = {}
        if self.organization:
            self._org_kwargs = {"org": self.organization}
            # E header para endpoints que não têm "org" na assinatura
            self.api_client.set_default_header("X-Organization", self.organization)

    # ------------------------------------------------------------------ #
    # Helpers básicos
    # ------------------------------------------------------------------ #
    def about(self) -> Dict[str, Any]:
        data, _ = self.api_client.server_api.retrieve_about(
            _request_timeout=self.timeout
        )
        return data.to_dict() if hasattr(data, "to_dict") else dict(data)

    # ------------------------------------------------------------------ #
    # Projetos
    # ------------------------------------------------------------------ #
    def _find_project_id_by_name(self, name: str) -> Optional[int]:
        page, _ = self.api_client.projects_api.list(
            search=name,
            _request_timeout=self.timeout,
            **self._org_kwargs,
        )

        for proj in page.results or []:
            if proj.name == name:
                return int(proj.id)
        return None

    def get_project_id(self, name: str) -> int:
        pid = self._find_project_id_by_name(name)
        if pid is None:
            raise ValueError(f"Projeto '{name}' não foi encontrado")
        return pid

    def get_or_create_project(self, name: str) -> int:
        pid = self._find_project_id_by_name(name)
        if pid is not None:
            return pid

        spec = models.ProjectWriteRequest(name=name)
        proj, _ = self.api_client.projects_api.create(
            spec,
            _request_timeout=self.timeout,
            **self._org_kwargs,
        )
        return int(proj.id)

    # ------------------------------------------------------------------ #
    # Tasks
    # ------------------------------------------------------------------ #
    def create_task(self, name: str, project_id: Optional[int] = None) -> int:
        spec = models.TaskWriteRequest(name=name, project_id=project_id)

        task, _ = self.api_client.tasks_api.create(
            spec,
            _request_timeout=self.timeout,
            **self._org_kwargs,
        )
        return int(task.id)

    # ------------------------------------------------------------------ #
    # Upload via TUS
    # ------------------------------------------------------------------ #
    def attach_data_to_task(
        self,
        task_id: int,
        images: List[Path],
        image_quality: int,
        chunk_size: int = 0,
    ) -> Optional[str]:
        """
        Anexa dados à task usando o fluxo TUS do endpoint:

          POST /api/tasks/{id}/data/

        1) Upload-Start    -> JSON, sem arquivos
        2) Upload-Multiple -> multipart/form-data, com arquivos
        3) Upload-Finish   -> JSON, sem arquivos

        Retorna o rq_id (se existir) para acompanhar em /api/requests/{rq_id}.
        """
        common_kwargs: Dict[str, Any] = {
            "image_quality": image_quality,
            "chunk_size": chunk_size,
        }

        tasks_api = self.api_client.tasks_api

        try:
            # 1) Upload-Start (somente metadados, sem arquivos)
            start_req = models.DataRequest(**common_kwargs)
            tasks_api.create_data(
                id=task_id,
                data_request=start_req,
                upload_start=True,
                _request_timeout=self.timeout,
                # NÃO passa **self._org_kwargs aqui; organização já está no header
            )

            # 2) Upload-Multiple (arquivos + campos simples) -> multipart/form-data
            files: List[Any] = []
            try:
                for img in images:
                    f = open(img, "rb")
                    files.append(f)

                multi_req = models.DataRequest(
                    client_files=files,
                    **common_kwargs,
                )

                tasks_api.create_data(
                    id=task_id,
                    data_request=multi_req,
                    upload_multiple=True,
                    _content_type="multipart/form-data",
                    _request_timeout=max(self.timeout, 300),
                )
            finally:
                # garante fechamento dos arquivos
                for f in files:
                    try:
                        f.close()
                    except Exception:
                        pass

            # 3) Upload-Finish (pode reenviar alguns metadados se quiser)
            finish_req = models.DataRequest(**common_kwargs)
            data, _ = tasks_api.create_data(
                id=task_id,
                data_request=finish_req,
                upload_finish=True,
                _request_timeout=self.timeout,
            )

            rq_id = getattr(data, "rq_id", None) or getattr(data, "request_id", None)
            return rq_id

        except exceptions.ApiException as e:
            raise RuntimeError(
                f"Falha ao anexar dados à task {task_id}: {e}"
            ) from e
