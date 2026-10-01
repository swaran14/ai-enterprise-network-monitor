def diagnose_device(
    status,
    latency=None,
    open_incidents=0,
    critical_alerts=0,
    warning_alerts=0,
    configuration_changed=False
):
    """
    Analyze network-device health and return
    troubleshooting recommendations.
    """

    status = (status or "unknown").lower()

    problems = []
    probable_causes = []
    recommendations = []

    severity = "INFO"

    # -----------------------------------------
    # RULE 1: DEVICE OFFLINE
    # -----------------------------------------

    if status == "offline":

        severity = "CRITICAL"

        problems.append(
            "Device is unreachable"
        )

        probable_causes.extend([
            "Device may be powered off",
            "Network interface may be down",
            "Network path may be unavailable",
            "IP address or routing may be incorrect"
        ])

        recommendations.extend([
            "Verify that the device is powered on",
            "Check physical and logical interface status",
            "Verify IP addressing and routing",
            "Test connectivity using ping"
        ])

    # -----------------------------------------
    # RULE 2: HIGH LATENCY
    # -----------------------------------------

    elif latency is not None and latency >= 200:

        severity = "CRITICAL"

        problems.append(
            "Very high network latency detected"
        )

        probable_causes.extend([
            "Severe network congestion",
            "Interface saturation",
            "Unstable network path"
        ])

        recommendations.extend([
            "Check interface utilization",
            "Inspect network traffic",
            "Check for packet loss or congestion"
        ])

    elif latency is not None and latency >= 100:

        severity = "WARNING"

        problems.append(
            "High network latency detected"
        )

        probable_causes.extend([
            "Network congestion",
            "High interface utilization",
            "Slow network path"
        ])

        recommendations.extend([
            "Monitor interface utilization",
            "Check traffic load",
            "Review recent latency history"
        ])

    # -----------------------------------------
    # RULE 3: CONFIGURATION CHANGE
    # -----------------------------------------

    if configuration_changed:

        if severity == "INFO":
            severity = "WARNING"

        problems.append(
            "Recent configuration change detected"
        )

        probable_causes.append(
            "A configuration modification may have affected device behavior"
        )

        recommendations.extend([
            "Review the latest configuration change",
            "Compare the current configuration with the previous backup"
        ])

    # -----------------------------------------
    # RULE 4: OPEN INCIDENTS
    # -----------------------------------------

    if open_incidents > 0:

        problems.append(
            f"{open_incidents} open incident(s) require attention"
        )

        recommendations.append(
            "Review unresolved alerts for this device"
        )

    # -----------------------------------------
    # RULE 5: CRITICAL/WARNING ALERTS
    # -----------------------------------------

    if critical_alerts > 0:

        severity = "CRITICAL"

        recommendations.append(
            "Prioritize investigation of critical alerts"
        )

    elif warning_alerts > 0 and severity == "INFO":

        severity = "WARNING"

    # -----------------------------------------
    # HEALTHY DEVICE
    # -----------------------------------------

    if not problems:

        problems.append(
            "No significant network problems detected"
        )

        probable_causes.append(
            "Device is operating normally"
        )

        recommendations.append(
            "Continue normal monitoring"
        )

    return {
        "severity": severity,
        "problems": problems,
        "probable_causes": probable_causes,
        "recommendations": recommendations
    }