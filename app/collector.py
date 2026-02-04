import asyncio
import httpx
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from .config import config, ServerConfig
from .database import db


class MetricsCollector:
    def __init__(self):
        self.vllm_config = config.vllm
        self.running = False
        self._current_server: Optional[ServerConfig] = config.get_default_server()
        self._previous_tokens: Dict[str, Dict[str, int]] = {}
        self._current_metrics: Dict[str, Any] = {}
        self._health_status: Dict[str, Any] = {
            "status": "unknown",
            "last_check": None,
            "error": None
        }
        self._models: list = []

    def get_current_server(self) -> Optional[ServerConfig]:
        return self._current_server

    def set_current_server(self, server_id: str) -> bool:
        server = config.get_server(server_id)
        if server:
            self._current_server = server
            self._current_metrics = {}
            self._health_status = {
                "status": "unknown",
                "last_check": None,
                "error": None
            }
            self._models = []
            return True
        return False

    def get_all_servers(self) -> list:
        return [
            {
                "id": s.id,
                "name": s.name,
                "host": s.host,
                "port": s.port,
                "base_url": s.base_url
            }
            for s in config.servers
        ]

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._current_server and self._current_server.api_key:
            headers["Authorization"] = f"Bearer {self._current_server.api_key}"
        return headers

    def _get_base_url(self) -> Optional[str]:
        if self._current_server:
            return self._current_server.base_url
        return None

    async def check_health(self) -> Dict[str, Any]:
        base_url = self._get_base_url()
        if not base_url:
            self._health_status = {
                "status": "no_server",
                "last_check": datetime.utcnow().isoformat(),
                "error": "No server configured"
            }
            return self._health_status

        try:
            async with httpx.AsyncClient(timeout=self.vllm_config.timeout) as client:
                response = await client.get(
                    f"{base_url}{self.vllm_config.health_endpoint}",
                    headers=self._get_headers()
                )
                if response.status_code == 200:
                    self._health_status = {
                        "status": "healthy",
                        "last_check": datetime.utcnow().isoformat(),
                        "error": None
                    }
                else:
                    self._health_status = {
                        "status": "unhealthy",
                        "last_check": datetime.utcnow().isoformat(),
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            self._health_status = {
                "status": "offline",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        return self._health_status

    async def fetch_models(self) -> list:
        base_url = self._get_base_url()
        if not base_url:
            return []

        try:
            async with httpx.AsyncClient(timeout=self.vllm_config.timeout) as client:
                response = await client.get(
                    f"{base_url}{self.vllm_config.models_endpoint}",
                    headers=self._get_headers()
                )
                if response.status_code == 200:
                    data = response.json()
                    self._models = data.get("data", [])
        except Exception:
            pass
        return self._models

    def _parse_prometheus_metrics(self, text: str) -> Dict[str, Any]:
        metrics = {}
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{?([^}]*)\}?\s+(.+)$', line)
            if match:
                name = match.group(1)
                labels = match.group(2)
                value = match.group(3)
                try:
                    value = float(value)
                except ValueError:
                    continue
                key = f"{name}_{{{labels}}}" if labels else name
                metrics[key] = {"name": name, "labels": labels, "value": value}
            else:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        metrics[parts[0]] = {
                            "name": parts[0],
                            "labels": "",
                            "value": float(parts[1])
                        }
                    except ValueError:
                        continue
        return metrics

    def _extract_token_metrics(self, metrics: Dict[str, Any]) -> Tuple[int, int, int, int]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        requests = 0

        for key, data in metrics.items():
            name = data["name"]
            value = data["value"]

            if "prompt_tokens" in name.lower() and "total" in name.lower():
                prompt_tokens = int(value)
            elif "generation_tokens" in name.lower() and "total" in name.lower():
                completion_tokens = int(value)
            elif "completion_tokens" in name.lower() and "total" in name.lower():
                completion_tokens = int(value)
            elif name == "vllm:num_requests_running":
                requests = int(value)
            elif "request" in name.lower() and "total" in name.lower():
                requests = max(requests, int(value))

        total_tokens = prompt_tokens + completion_tokens
        return prompt_tokens, completion_tokens, total_tokens, requests

    async def fetch_metrics(self) -> Dict[str, Any]:
        base_url = self._get_base_url()
        if not base_url:
            return {
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "error": "No server configured"
            }

        server_id = self._current_server.id if self._current_server else "unknown"

        try:
            async with httpx.AsyncClient(timeout=self.vllm_config.timeout) as client:
                response = await client.get(
                    f"{base_url}{self.vllm_config.metrics_endpoint}",
                    headers=self._get_headers()
                )
                if response.status_code == 200:
                    raw_metrics = self._parse_prometheus_metrics(response.text)
                    self._current_metrics = raw_metrics

                    prompt, completion, total, requests = self._extract_token_metrics(raw_metrics)

                    prev = self._previous_tokens.get(server_id, {})
                    prev_prompt = prev.get("prompt", 0)
                    prev_completion = prev.get("completion", 0)
                    prev_requests = prev.get("requests", 0)

                    delta_prompt = max(0, prompt - prev_prompt)
                    delta_completion = max(0, completion - prev_completion)
                    delta_total = delta_prompt + delta_completion
                    delta_requests = max(0, requests - prev_requests)

                    self._previous_tokens[server_id] = {
                        "prompt": prompt,
                        "completion": completion,
                        "requests": requests
                    }

                    if delta_total > 0 or delta_requests > 0:
                        await db.insert_token_stats(
                            server_id, delta_prompt, delta_completion, delta_total, delta_requests
                        )

                    for key, data in raw_metrics.items():
                        if any(kw in data["name"].lower() for kw in
                               ["latency", "tokens", "requests", "gpu", "cache", "queue"]):
                            await db.insert_metric(
                                server_id, data["name"], data["value"], data["labels"]
                            )

                    return {
                        "success": True,
                        "timestamp": datetime.utcnow().isoformat(),
                        "server_id": server_id,
                        "metrics_count": len(raw_metrics),
                        "tokens": {
                            "prompt": prompt,
                            "completion": completion,
                            "total": total,
                            "delta_prompt": delta_prompt,
                            "delta_completion": delta_completion,
                            "delta_total": delta_total
                        },
                        "requests": requests
                    }
        except Exception as e:
            return {
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def get_current_metrics(self) -> Dict[str, Any]:
        return self._current_metrics

    async def get_health_status(self) -> Dict[str, Any]:
        return self._health_status

    async def get_models(self) -> list:
        return self._models

    async def start_collection_loop(self):
        self.running = True
        while self.running:
            await self.check_health()
            await self.fetch_metrics()
            await self.fetch_models()
            await db.cleanup_old_data()
            await asyncio.sleep(config.monitor.polling_interval)

    def stop(self):
        self.running = False


collector = MetricsCollector()
