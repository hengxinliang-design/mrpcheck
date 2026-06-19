"""Reserved ERP function test client.

These endpoints are intentionally disabled by default. They provide stable
request/response shapes for later ERP API integration without making any real
ERP calls before the ERP team provides base URL and authentication details.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ERPTestClientNotConfigured(RuntimeError):
    pass


@dataclass
class ERPTestClient:
    cfg: dict

    def _settings(self) -> dict:
        return self.cfg.get("erp_api", {})

    def ensure_enabled(self) -> dict:
        settings = self._settings()
        if not settings.get("enabled", False):
            raise ERPTestClientNotConfigured(
                "ERP function test API is reserved but not enabled. "
                "Set erp_api.enabled=true and configure base_url/endpoints after ERP provides the API."
            )
        base_url = settings.get("base_url", "")
        if not base_url or "<" in base_url:
            raise ERPTestClientNotConfigured("ERP API base_url is not configured.")
        return settings

    def datacheck(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("datacheck", payload)

    def master_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("master_data", payload)

    def import_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("import_plan", payload)

    def run_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("run_plan", payload)

    def _post(self, endpoint_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.ensure_enabled()
        endpoints = settings.get("endpoints", {})
        path = endpoints.get(endpoint_key)
        if not path:
            raise ERPTestClientNotConfigured(f"ERP API endpoint not configured: {endpoint_key}")

        with httpx.Client(base_url=settings["base_url"], timeout=settings.get("timeout_seconds", 30)) as client:
            resp = client.post(path, json=payload, headers=self._headers(settings))
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _headers(settings: dict) -> dict[str, str]:
        auth = settings.get("auth", {})
        if auth.get("type") == "api_key" and auth.get("header_name") and auth.get("api_key"):
            return {auth["header_name"]: auth["api_key"]}
        return {}

