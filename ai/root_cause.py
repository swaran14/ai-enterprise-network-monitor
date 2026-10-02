def analyze_root_cause(
    status,
    latency=None,
    open_incidents=0,
    critical_alerts=0,
    warning_alerts=0,
    configuration_changed=False
):
    status = (status or "unknown").lower()

    evidence = []

    # -----------------------------------
    # CONFIGURATION-RELATED FAILURE
    # -----------------------------------

    if configuration_changed and (
        status == "offline"
        or critical_alerts > 0
        or warning_alerts > 0
    ):
        evidence.append(
            "Recent configuration change detected"
        )

        if critical_alerts > 0:
            evidence.append(
                f"{critical_alerts} critical alert(s) are open"
            )

        if status == "offline":
            evidence.append(
                "Device is currently unreachable"
            )

        return {
            "root_cause": "Possible configuration-related network issue",
            "confidence": "HIGH",
            "evidence": evidence,
            "recommended_action": (
                "Review the latest configuration diff and "
                "consider restoring the previous known-good configuration."
            )
        }

    # -----------------------------------
    # DEVICE CONNECTIVITY FAILURE
    # -----------------------------------

    if status == "offline":
        evidence.append(
            "Device failed connectivity monitoring"
        )

        if open_incidents > 0:
            evidence.append(
                f"{open_incidents} incident(s) remain open"
            )

        return {
            "root_cause": "Possible device or network connectivity failure",
            "confidence": "HIGH",
            "evidence": evidence,
            "recommended_action": (
                "Verify power, interfaces, cabling, IP configuration, "
                "gateway and routing."
            )
        }

    # -----------------------------------
    # SEVERE PERFORMANCE ISSUE
    # -----------------------------------

    if latency is not None and latency >= 200:
        evidence.append(
            f"Current latency is {latency} ms"
        )

        return {
            "root_cause": "Possible severe network congestion",
            "confidence": "HIGH",
            "evidence": evidence,
            "recommended_action": (
                "Inspect interface utilization, packet loss and traffic load."
            )
        }

    # -----------------------------------
    # MODERATE PERFORMANCE ISSUE
    # -----------------------------------

    if latency is not None and latency >= 100:
        evidence.append(
            f"Current latency is {latency} ms"
        )

        return {
            "root_cause": "Possible network congestion or slow path",
            "confidence": "MEDIUM",
            "evidence": evidence,
            "recommended_action": (
                "Review latency history and interface utilization."
            )
        }

    # -----------------------------------
    # ACTIVE ALERTS
    # -----------------------------------

    if critical_alerts > 0:
        evidence.append(
            f"{critical_alerts} critical alert(s) are still open"
        )

        return {
            "root_cause": "Unresolved critical network incident",
            "confidence": "MEDIUM",
            "evidence": evidence,
            "recommended_action": (
                "Investigate the open critical incidents and verify recovery."
            )
        }

    if warning_alerts > 0:
        evidence.append(
            f"{warning_alerts} warning alert(s) are open"
        )

        return {
            "root_cause": "Possible network performance degradation",
            "confidence": "MEDIUM",
            "evidence": evidence,
            "recommended_action": (
                "Review warning alerts and recent performance metrics."
            )
        }

    # -----------------------------------
    # HEALTHY DEVICE
    # -----------------------------------

    return {
        "root_cause": "No active fault identified",
        "confidence": "HIGH",
        "evidence": [
            "Device is operating within normal monitored conditions"
        ],
        "recommended_action": "Continue normal monitoring."
    }