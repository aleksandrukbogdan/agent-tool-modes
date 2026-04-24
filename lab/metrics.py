def summarize(rows):
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "success": 0.0,
            "mean_prompt_tokens": 0.0,
            "mean_completion_tokens": 0.0,
            "mean_total_tokens": 0.0,
            "mean_latency_s": 0.0,
            "median_latency_s": 0.0,
            "mean_model_calls": 0.0,
            "mean_tool_calls": 0.0,
            "tool_errors": 0,
            "by_family": {},
        }

    def mean(key):
        return sum(row[key] for row in rows) / n

    latencies = sorted(row["latency_s"] for row in rows)
    if n % 2:
        median = latencies[n // 2]
    else:
        median = (latencies[n // 2 - 1] + latencies[n // 2]) / 2
    families = {}
    for row in rows:
        bucket = families.setdefault(row["family"], [0, 0])
        bucket[0] += 1
        bucket[1] += 1 if row["ok"] else 0
    return {
        "n": n,
        "success": sum(1 for row in rows if row["ok"]) / n,
        "mean_prompt_tokens": mean("prompt_tokens"),
        "mean_completion_tokens": mean("completion_tokens"),
        "mean_total_tokens": sum(row["prompt_tokens"] + row["completion_tokens"] for row in rows) / n,
        "mean_latency_s": mean("latency_s"),
        "median_latency_s": median,
        "mean_model_calls": mean("model_calls"),
        "mean_tool_calls": mean("tool_calls"),
        "tool_errors": sum(row["tool_errors"] for row in rows),
        "by_family": {
            name: {"n": counts[0], "success": counts[1] / counts[0]} for name, counts in families.items()
        },
    }
