"""CloudWatch Embedded Metric Format. Local runs just log a line."""

from __future__ import annotations

import json
import os
import time


def emit(values: dict[str, float], unit: str = "Count") -> None:
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return
    metrics = [{"Name": name, "Unit": unit} for name in values]
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "MandiLens",
                    "Dimensions": [["Service"]],
                    "Metrics": metrics,
                }
            ],
        },
        "Service": "mandilens",
    }
    payload.update(values)
    print(json.dumps(payload))
