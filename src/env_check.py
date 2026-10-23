"""Smoke test môi trường: Spark version + một phép tính Spark. PASS -> exit 0."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "env_check.txt"


def java_version() -> str:
    try:
        proc = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=30)
        lines = (proc.stderr or proc.stdout).strip().splitlines()
        return lines[0] if lines else "unknown"
    except Exception as exc:
        return f"FAIL - {type(exc).__name__}"


def finish(lines: list[str], status: str) -> None:
    lines.append(f"RESULT   : {status}")
    text = "\n".join(lines) + "\n\n"
    print(text, end="")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    lines = [
        f"=== env_check {datetime.now(timezone.utc).isoformat(timespec='seconds')} ===",
        f"Python   : {sys.version.split()[0]}",
        f"JAVA_HOME: {os.environ.get('JAVA_HOME', '(chưa set)')}",
        f"Java     : {java_version()}",
    ]
    spark = None
    status = "FAIL"
    try:
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder.master("local[*]")
            .appName("env-check")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
        count = spark.range(1_000_000).count()
        lines += [f"Spark    : {spark.version}", f"Count    : {count}"]
        status = "PASS" if count == 1_000_000 else "FAIL"
    except Exception as exc:
        lines.append(f"Spark    : FAIL - {type(exc).__name__}: {exc}")
    finally:
        if spark is not None:
            spark.stop()

    finish(lines, status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
