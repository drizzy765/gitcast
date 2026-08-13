#!/usr/bin/env python3
"""
Gitcast Development Benchmark & Diagnostics Tool.
Measures execution latency and payload processing throughput.
"""

import time
import json
from pathlib import Path
from datetime import datetime

from config.settings import (
    GITCAST_API_URL,
    BYOK_KEY,
    BYOK_PROVIDER,
    STORAGE_DIR,
    DEFAULTS,
)
from api.payload import build_payload, validate_payload
from ai.viral_patterns import get_all_patterns


def benchmark_payload_construction(iterations: int = 500) -> float:
    print(f"[Benchmark] Measuring payload construction ({iterations} iterations)...")
    capture = {
        "screenshot": {"path": str(STORAGE_DIR / "sample.png"), "timestamp": datetime.now().isoformat()},
        "git_diff": {"diff": "diff --git a/main.py b/main.py\n+print('hello')\n"},
    }
    ocr = {"text": "def main(): print('hello')", "raw_text": "main()"}
    project_ctx = {"project_name": "gitcast", "readme_content": "# Gitcast\nAutomated posts"}

    start_time = time.perf_counter()
    for _ in range(iterations):
        payload = build_payload(
            raw_thought="Working on benchmark improvements",
            ocr_result=ocr,
            capture_result=capture,
            project_ctx=project_ctx,
        )
        _ = validate_payload(payload)
    elapsed = time.perf_counter() - start_time
    avg_ms = (elapsed / iterations) * 1000
    print(f"[Benchmark] Completed in {elapsed:.4f}s (Average: {avg_ms:.3f} ms/iter)")
    return elapsed


def benchmark_pattern_matching(iterations: int = 1000) -> float:
    print(f"[Benchmark] Measuring viral pattern matching ({iterations} iterations)...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        patterns = get_all_patterns()
        _ = len(patterns)
    elapsed = time.perf_counter() - start_time
    avg_ms = (elapsed / iterations) * 1000
    print(f"[Benchmark] Completed in {elapsed:.4f}s (Average: {avg_ms:.3f} ms/iter)")
    return elapsed


def run_diagnostics() -> dict:
    print("[Diagnostics] Running Gitcast configuration check...")
    results = {
        "api_url": GITCAST_API_URL,
        "has_byok": bool(BYOK_KEY),
        "byok_provider": BYOK_PROVIDER,
        "storage_dir_exists": STORAGE_DIR.exists(),
        "default_settings_keys": list(DEFAULTS.keys()),
        "timestamp": datetime.now().isoformat(),
    }
    print(f"[Diagnostics] API URL: {results['api_url']}")
    print(f"[Diagnostics] Storage Dir Ready: {results['storage_dir_exists']}")
    return results


def main():
    print("=" * 60)
    print(" Gitcast Developer Benchmark & Diagnostic Suite ")
    print("=" * 60)
    run_diagnostics()
    print("-" * 60)
    benchmark_payload_construction(500)
    print("-" * 60)
    benchmark_pattern_matching(1000)
    print("=" * 60)
    print(" Diagnostic & Benchmark Complete ")
    print("=" * 60)


if __name__ == "__main__":
    main()
