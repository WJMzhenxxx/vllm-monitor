import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from .config import config


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.monitor.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    server_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    labels TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS token_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    server_id TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    requests INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    server_id TEXT NOT NULL,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    latency_ms REAL,
                    status TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                ON metrics(timestamp)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_server
                ON metrics(server_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_stats_timestamp
                ON token_stats(timestamp)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_stats_server
                ON token_stats(server_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp
                ON request_logs(timestamp)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_logs_server
                ON request_logs(server_id)
            """)
            await db.commit()

    async def insert_metric(self, server_id: str, name: str, value: float, labels: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO metrics (server_id, metric_name, metric_value, labels) VALUES (?, ?, ?, ?)",
                (server_id, name, value, labels)
            )
            await db.commit()

    async def insert_token_stats(self, server_id: str, prompt_tokens: int, completion_tokens: int,
                                  total_tokens: int, requests: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO token_stats
                   (server_id, prompt_tokens, completion_tokens, total_tokens, requests)
                   VALUES (?, ?, ?, ?, ?)""",
                (server_id, prompt_tokens, completion_tokens, total_tokens, requests)
            )
            await db.commit()

    async def insert_request_log(self, server_id: str, model: str, prompt_tokens: int,
                                  completion_tokens: int, latency_ms: float, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO request_logs
                   (server_id, model, prompt_tokens, completion_tokens, latency_ms, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (server_id, model, prompt_tokens, completion_tokens, latency_ms, status)
            )
            await db.commit()

    async def get_metrics_history(self, server_id: str, metric_name: str, hours: int = 1,
                                   limit: int = None) -> List[Dict[str, Any]]:
        limit = limit or config.dashboard.chart_points
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute(
                """SELECT timestamp, metric_value
                   FROM metrics
                   WHERE server_id = ? AND metric_name = ? AND timestamp > ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (server_id, metric_name, cutoff.isoformat(), limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    async def get_token_stats_history(self, server_id: str, hours: int = 1,
                                       limit: int = None) -> List[Dict[str, Any]]:
        limit = limit or config.dashboard.chart_points
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute(
                """SELECT timestamp, prompt_tokens, completion_tokens,
                          total_tokens, requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (server_id, cutoff.isoformat(), limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    async def get_token_totals(self, server_id: str, hours: int = 24) -> Dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute(
                """SELECT
                      COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                      COALESCE(SUM(completion_tokens), 0) as total_completion,
                      COALESCE(SUM(total_tokens), 0) as total,
                      COALESCE(SUM(requests), 0) as total_requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?""",
                (server_id, cutoff.isoformat(),)
            )
            row = await cursor.fetchone()
            return {
                "prompt_tokens": row[0],
                "completion_tokens": row[1],
                "total_tokens": row[2],
                "requests": row[3]
            }

    async def get_recent_requests(self, server_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM request_logs
                   WHERE server_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (server_id, limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def cleanup_old_data(self, hours: int = None):
        hours = hours or config.monitor.history_retention_hours
        async with aiosqlite.connect(self.db_path) as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            await db.execute("DELETE FROM metrics WHERE timestamp < ?",
                           (cutoff.isoformat(),))
            await db.execute("DELETE FROM token_stats WHERE timestamp < ?",
                           (cutoff.isoformat(),))
            await db.execute("DELETE FROM request_logs WHERE timestamp < ?",
                           (cutoff.isoformat(),))
            await db.commit()

    async def get_daily_stats(self, server_id: str, days: int = 7) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.utcnow() - timedelta(days=days)
            cursor = await db.execute(
                """SELECT
                      DATE(timestamp) as date,
                      SUM(prompt_tokens) as prompt_tokens,
                      SUM(completion_tokens) as completion_tokens,
                      SUM(total_tokens) as total_tokens,
                      SUM(requests) as requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?
                   GROUP BY DATE(timestamp)
                   ORDER BY date ASC""",
                (server_id, cutoff.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_hourly_stats(self, server_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute(
                """SELECT
                      strftime('%Y-%m-%d %H:00', timestamp) as hour,
                      SUM(prompt_tokens) as prompt_tokens,
                      SUM(completion_tokens) as completion_tokens,
                      SUM(total_tokens) as total_tokens,
                      SUM(requests) as requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?
                   GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
                   ORDER BY hour ASC""",
                (server_id, cutoff.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_weekly_report(self, server_id: str) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow()

            # Current week stats
            week_start = now - timedelta(days=7)
            cursor = await db.execute(
                """SELECT
                      COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                      COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                      COALESCE(SUM(total_tokens), 0) as total_tokens,
                      COALESCE(SUM(requests), 0) as requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?""",
                (server_id, week_start.isoformat())
            )
            current_week = await cursor.fetchone()

            # Previous week stats for comparison
            prev_week_start = now - timedelta(days=14)
            prev_week_end = now - timedelta(days=7)
            cursor = await db.execute(
                """SELECT
                      COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                      COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                      COALESCE(SUM(total_tokens), 0) as total_tokens,
                      COALESCE(SUM(requests), 0) as requests
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ? AND timestamp <= ?""",
                (server_id, prev_week_start.isoformat(), prev_week_end.isoformat())
            )
            previous_week = await cursor.fetchone()

            # Peak usage day
            cursor = await db.execute(
                """SELECT
                      DATE(timestamp) as date,
                      SUM(total_tokens) as total_tokens
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?
                   GROUP BY DATE(timestamp)
                   ORDER BY total_tokens DESC
                   LIMIT 1""",
                (server_id, week_start.isoformat())
            )
            peak_day = await cursor.fetchone()

            # Peak usage hour
            cursor = await db.execute(
                """SELECT
                      strftime('%H', timestamp) as hour,
                      SUM(total_tokens) as total_tokens
                   FROM token_stats
                   WHERE server_id = ? AND timestamp > ?
                   GROUP BY strftime('%H', timestamp)
                   ORDER BY total_tokens DESC
                   LIMIT 1""",
                (server_id, week_start.isoformat())
            )
            peak_hour = await cursor.fetchone()

            # Calculate averages
            daily_stats = await self.get_daily_stats(server_id, days=7)
            days_with_data = len(daily_stats) or 1

            def calc_change(current, previous):
                if previous == 0:
                    return 100.0 if current > 0 else 0.0
                return ((current - previous) / previous) * 100

            return {
                "period": {
                    "start": week_start.isoformat(),
                    "end": now.isoformat()
                },
                "current_week": {
                    "prompt_tokens": current_week[0],
                    "completion_tokens": current_week[1],
                    "total_tokens": current_week[2],
                    "requests": current_week[3]
                },
                "previous_week": {
                    "prompt_tokens": previous_week[0],
                    "completion_tokens": previous_week[1],
                    "total_tokens": previous_week[2],
                    "requests": previous_week[3]
                },
                "change": {
                    "prompt_tokens": calc_change(current_week[0], previous_week[0]),
                    "completion_tokens": calc_change(current_week[1], previous_week[1]),
                    "total_tokens": calc_change(current_week[2], previous_week[2]),
                    "requests": calc_change(current_week[3], previous_week[3])
                },
                "averages": {
                    "daily_tokens": current_week[2] / days_with_data,
                    "daily_requests": current_week[3] / days_with_data
                },
                "peak": {
                    "day": peak_day[0] if peak_day else None,
                    "day_tokens": peak_day[1] if peak_day else 0,
                    "hour": f"{peak_hour[0]}:00" if peak_hour else None,
                    "hour_tokens": peak_hour[1] if peak_hour else 0
                },
                "daily_breakdown": daily_stats
            }


db = Database()
