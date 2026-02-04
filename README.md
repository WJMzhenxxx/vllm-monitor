# vLLM Monitor

A professional real-time monitoring dashboard for vLLM services with token input/output tracking.

## Features

- **Real-time Token Tracking**: Monitor prompt and completion tokens in real-time
- **Professional Dashboard**: Modern, responsive web UI with charts and metrics
- **Historical Data**: View token usage trends over 1h, 6h, or 24h periods
- **System Status**: Monitor vLLM health, running/pending requests, GPU utilization
- **Raw Metrics**: View and filter all Prometheus metrics from vLLM
- **Configurable**: All settings via `config.json`

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Edit `config.json` to set your vLLM service URL:

```json
{
  "vllm": {
    "host": "localhost",
    "port": 8000,
    "api_key": "",
    "ssl": false
  }
}
```

### 3. Run

```bash
python run.py
```

Open http://localhost:8080 in your browser.

## Configuration

All settings are in `config.json`:

### vLLM Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | vLLM server hostname | `localhost` |
| `port` | vLLM server port | `8000` |
| `api_key` | API key for authentication (optional) | `""` |
| `ssl` | Use HTTPS | `false` |
| `timeout` | Request timeout in seconds | `30` |
| `metrics_endpoint` | Prometheus metrics endpoint | `/metrics` |
| `health_endpoint` | Health check endpoint | `/health` |
| `models_endpoint` | Models list endpoint | `/v1/models` |

### Monitor Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `polling_interval` | How often to poll vLLM (seconds) | `5` |
| `history_retention_hours` | How long to keep historical data | `24` |
| `database_path` | SQLite database location | `data/metrics.db` |

### Dashboard Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | Dashboard server host | `0.0.0.0` |
| `port` | Dashboard server port | `8080` |
| `refresh_interval` | UI refresh rate (seconds) | `5` |
| `chart_points` | Max data points in charts | `100` |

### Alerts Settings (Optional)

| Setting | Description | Default |
|---------|-------------|---------|
| `enabled` | Enable alerting | `false` |
| `token_rate_threshold` | Alert if tokens/interval exceeds | `10000` |
| `latency_threshold_ms` | Alert if latency exceeds (ms) | `5000` |
| `webhook_url` | Webhook URL for alerts | `""` |

## API Endpoints

The dashboard exposes several API endpoints:

- `GET /api/health` - vLLM health status
- `GET /api/models` - List of loaded models
- `GET /api/metrics/current` - Current raw metrics
- `GET /api/metrics/tokens?hours=1` - Token usage history
- `GET /api/stats/summary` - Summary statistics
- `GET /api/config` - Current configuration

## Project Structure

```
vllm-monitor/
├── app/
│   ├── __init__.py
│   ├── config.py       # Configuration management
│   ├── database.py     # SQLite database operations
│   ├── collector.py    # vLLM metrics collection
│   └── main.py         # FastAPI application
├── static/
│   ├── css/
│   │   └── styles.css  # Dashboard styles
│   └── js/
│       └── dashboard.js # Dashboard JavaScript
├── templates/
│   └── dashboard.html  # Dashboard HTML template
├── data/               # Database storage
├── config.json         # Configuration file
├── requirements.txt    # Python dependencies
├── run.py              # Entry point
└── README.md
```

## Requirements

- Python 3.8+
- vLLM server with metrics enabled (`--enable-metrics`)

## License

MIT
