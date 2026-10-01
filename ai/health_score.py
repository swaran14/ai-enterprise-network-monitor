def calculate_health_score(
    status,
    latency=None,
    open_incidents=0,
    critical_alerts=0,
    warning_alerts=0,
    configuration_changed=False
):
    score = 100

    status = (status or "unknown").lower()

    # Device availability
    if status == "offline":
        score -= 50

    elif status == "unknown":
        score -= 20

    # Latency
    if latency is not None:

        if latency >= 200:
            score -= 30

        elif latency >= 100:
            score -= 15

        elif latency >= 50:
            score -= 5

    # Incidents
    score -= min(open_incidents * 5, 20)

    # Alerts
    score -= min(critical_alerts * 10, 30)
    score -= min(warning_alerts * 5, 15)

    # Configuration change
    if configuration_changed:
        score -= 10

    # Keep score between 0 and 100
    score = max(0, min(score, 100))

    # Health classification
    if score >= 90:
        health = "EXCELLENT"

    elif score >= 75:
        health = "GOOD"

    elif score >= 50:
        health = "DEGRADED"

    elif score >= 25:
        health = "POOR"

    else:
        health = "CRITICAL"

    return {
        "score": score,
        "health": health
    }