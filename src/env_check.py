"""Smoke test môi trường – Đồ án 2 Checkpoint 2.

PASS khi: in được Spark version + một phép tính Spark chạy thành công.
Evidence được append vào logs/env_check.txt.

Chạy:  python src/env_check.py
Mã thoát: 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"


def java_version() -> str:
    """java -version ghi ra stderr nên đọc cả hai."""
    try:
        proc = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=30
        )
        out = (proc.stderr or proc.stdout).strip().splitlines()
        return out[0] if out else "java: không thấy output"
    except FileNotFoundError:
        return "java: KHÔNG TÌM THẤY (kiểm tra PATH / JAVA_HOME)"
    except subprocess.TimeoutExpired:
        return "java: timeout khi gọi java -version"


def finish(lines: list[str], status: str) -> None:
    lines.append(f"RESULT : {status}")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "env_check.txt").open("a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def main() -> int:
    lines = [
        f"=== env_check {datetime.now(timezone.utc).isoformat(timespec='seconds')} ===",
        f"Python   : {sys.version.split()[0]} ({sys.executable})",
        f"JAVA_HOME: {os.environ.get('JAVA_HOME', '(chưa set)')}",
        f"Java     : {java_version()}",
    ]

    try:
        import pyspark  # noqa: F401
        from pyspark.sql import SparkSession
    except ImportError as exc:
        lines.append(f"PySpark  : FAIL – {exc} (chạy: pip install -r requirements.txt)")
        finish(lines, status="FAIL")
        return 1

    spark = None
    status = "FAIL"
    try:
        spark = (
            SparkSession.builder.master("local[*]")
            .appName("env-check")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
        count = spark.range(1_000_000).count()
        lines.append(f"Spark    : {spark.version}")
        lines.append(f"Count    : {count} (mong đợi 1000000)")
        status = "PASS" if count == 1_000_000 else "FAIL"
    except Exception as exc:  # noqa: BLE001 – muốn bắt mọi lỗi runtime của Spark
        lines.append(f"Spark    : FAIL – {type(exc).__name__}: {exc}")
        lines.append("Gợi ý: java -version/JAVA_HOME -> python --version -> import pyspark")
    finally:
        if spark is not None:
            spark.stop()

    finish(lines, status=status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
