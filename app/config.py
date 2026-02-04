import json
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional


class ServerConfig(BaseModel):
    id: str
    name: str
    host: str = "localhost"
    port: int = 8000
    api_key: str = ""
    ssl: bool = False

    @property
    def base_url(self) -> str:
        protocol = "https" if self.ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"


class VLLMConfig(BaseModel):
    timeout: int = 30
    metrics_endpoint: str = "/metrics"
    health_endpoint: str = "/health"
    models_endpoint: str = "/v1/models"


class MonitorConfig(BaseModel):
    polling_interval: int = 5
    history_retention_hours: int = 24
    database_path: str = "data/metrics.db"


class DashboardConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    refresh_interval: int = 5
    chart_points: int = 100


class AlertsConfig(BaseModel):
    enabled: bool = False
    token_rate_threshold: int = 10000
    latency_threshold_ms: int = 5000
    webhook_url: str = ""


class AppConfig(BaseModel):
    servers: List[ServerConfig] = []
    default_server: str = ""
    vllm: VLLMConfig = VLLMConfig()
    monitor: MonitorConfig = MonitorConfig()
    dashboard: DashboardConfig = DashboardConfig()
    alerts: AlertsConfig = AlertsConfig()

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        for server in self.servers:
            if server.id == server_id:
                return server
        return None

    def get_default_server(self) -> Optional[ServerConfig]:
        if self.default_server:
            return self.get_server(self.default_server)
        if self.servers:
            return self.servers[0]
        return None


def load_config(config_path: str = "config.json") -> AppConfig:
    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        return AppConfig(**data)
    return AppConfig()


config = load_config()
