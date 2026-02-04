import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel

from .config import config
from .database import db
from .collector import collector


class ServerSwitchRequest(BaseModel):
    server_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    collection_task = asyncio.create_task(collector.start_collection_loop())
    yield
    collector.stop()
    collection_task.cancel()
    try:
        await collection_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="vLLM Monitor",
    description="Real-time monitoring dashboard for vLLM services",
    version="1.0.0",
    lifespan=lifespan
)

BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "config": config
    })


@app.get("/api/servers")
async def api_servers():
    current = collector.get_current_server()
    return {
        "servers": collector.get_all_servers(),
        "current": current.id if current else None
    }


@app.post("/api/servers/switch")
async def api_switch_server(request: ServerSwitchRequest):
    success = collector.set_current_server(request.server_id)
    if success:
        await collector.check_health()
        await collector.fetch_metrics()
        await collector.fetch_models()
        current = collector.get_current_server()
        return {
            "success": True,
            "server": {
                "id": current.id,
                "name": current.name,
                "base_url": current.base_url
            } if current else None
        }
    return JSONResponse(
        status_code=404,
        content={"success": False, "error": "Server not found"}
    )


@app.get("/api/health")
async def api_health():
    health = await collector.get_health_status()
    current = collector.get_current_server()
    return {
        **health,
        "server_id": current.id if current else None,
        "server_name": current.name if current else None
    }


@app.get("/api/models")
async def api_models():
    return {"models": await collector.get_models()}


@app.get("/api/metrics/current")
async def api_current_metrics():
    metrics = await collector.get_current_metrics()
    return {"metrics": metrics}


@app.get("/api/metrics/tokens")
async def api_token_metrics(hours: int = 1):
    current = collector.get_current_server()
    if not current:
        return {"history": [], "totals": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}}

    history = await db.get_token_stats_history(current.id, hours=hours)
    totals = await db.get_token_totals(current.id, hours=hours)
    return {
        "history": history,
        "totals": totals
    }


@app.get("/api/metrics/history/{metric_name}")
async def api_metric_history(metric_name: str, hours: int = 1):
    current = collector.get_current_server()
    if not current:
        return {"metric": metric_name, "history": []}

    history = await db.get_metrics_history(current.id, metric_name, hours=hours)
    return {"metric": metric_name, "history": history}


@app.get("/api/requests/recent")
async def api_recent_requests(limit: int = 50):
    current = collector.get_current_server()
    if not current:
        return {"requests": []}

    requests = await db.get_recent_requests(current.id, limit=limit)
    return {"requests": requests}


@app.get("/api/stats/summary")
async def api_stats_summary():
    health = await collector.get_health_status()
    current = collector.get_current_server()
    models = await collector.get_models()
    metrics = await collector.get_current_metrics()

    if current:
        totals_1h = await db.get_token_totals(current.id, hours=1)
        totals_24h = await db.get_token_totals(current.id, hours=24)
    else:
        totals_1h = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}
        totals_24h = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}

    gpu_utilization = None
    cache_usage = None
    running_requests = None
    pending_requests = None

    for key, data in metrics.items():
        name = data["name"].lower()
        if "gpu" in name and "utilization" in name:
            gpu_utilization = data["value"]
        elif "cache" in name and ("hit" in name or "usage" in name):
            cache_usage = data["value"]
        elif "running" in name:
            running_requests = int(data["value"])
        elif "pending" in name or "waiting" in name:
            pending_requests = int(data["value"])

    return {
        "health": health,
        "server": {
            "id": current.id,
            "name": current.name,
            "base_url": current.base_url
        } if current else None,
        "models": [m.get("id", "unknown") for m in models],
        "tokens": {
            "last_hour": totals_1h,
            "last_24h": totals_24h
        },
        "system": {
            "gpu_utilization": gpu_utilization,
            "cache_usage": cache_usage,
            "running_requests": running_requests,
            "pending_requests": pending_requests
        },
        "config": {
            "polling_interval": config.monitor.polling_interval
        }
    }


@app.get("/api/config")
async def api_config():
    current = collector.get_current_server()
    return {
        "server": {
            "id": current.id,
            "name": current.name,
            "host": current.host,
            "port": current.port,
            "base_url": current.base_url
        } if current else None,
        "monitor": {
            "polling_interval": config.monitor.polling_interval,
            "history_retention_hours": config.monitor.history_retention_hours
        },
        "dashboard": {
            "refresh_interval": config.dashboard.refresh_interval,
            "chart_points": config.dashboard.chart_points
        }
    }


@app.get("/api/reports/weekly")
async def api_weekly_report():
    current = collector.get_current_server()
    if not current:
        return {"error": "No server selected"}

    report = await db.get_weekly_report(current.id)
    report["server"] = {
        "id": current.id,
        "name": current.name
    }
    return report


@app.get("/api/reports/daily")
async def api_daily_stats(days: int = 7):
    current = collector.get_current_server()
    if not current:
        return {"daily": []}

    daily = await db.get_daily_stats(current.id, days=days)
    return {"daily": daily}


@app.get("/api/reports/hourly")
async def api_hourly_stats(hours: int = 168):
    current = collector.get_current_server()
    if not current:
        return {"hourly": []}

    hourly = await db.get_hourly_stats(current.id, hours=hours)
    return {"hourly": hourly}
