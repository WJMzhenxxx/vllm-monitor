#!/usr/bin/env python3
"""
vLLM Monitor - Real-time monitoring dashboard for vLLM services.

Usage:
    python run.py [--config CONFIG_PATH]
"""
import argparse
import uvicorn
from app.config import load_config


def main():
    parser = argparse.ArgumentParser(description="vLLM Monitor Dashboard")
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    parser.add_argument(
        "--host",
        help="Override dashboard host"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        help="Override dashboard port"
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Override with CLI args if provided
    host = args.host or config.dashboard.host
    port = args.port or config.dashboard.port

    # Get default server info
    default_server = config.get_default_server()
    server_info = default_server.base_url if default_server else "No servers configured"
    server_count = len(config.servers)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                     vLLM Monitor v1.0                        ║
╠══════════════════════════════════════════════════════════════╣
║  Dashboard:  http://{host}:{port:<5}                           ║
║  Servers:    {server_count} configured                                   ║
║  Default:    {server_info:<35}      ║
║  Polling:    Every {config.monitor.polling_interval}s                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
