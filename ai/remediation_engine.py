def recommend_remediation(
    status,
    latency=None,
    critical_alerts=0,
    warning_alerts=0,
    configuration_changed=False
):
    status = (status or "unknown").lower()

    # -----------------------------------
    # CONFIGURATION-RELATED PROBLEM
    # -----------------------------------

    if configuration_changed and (
        status == "offline"
        or critical_alerts > 0
        or warning_alerts > 0
    ):
        return {
            "action": "REVIEW_CONFIG_DIFF",
            "title": "Review recent configuration changes",
            "reason": (
                "A recent configuration change may be related "
                "to the current network problem."
            ),
            "risk": "MEDIUM",
            "requires_approval": True,
            "automatic_execution": False,
            "suggested_commands": [
                "show running-config",
                "show startup-config",
                "show ip interface brief"
            ]
        }

    # -----------------------------------
    # DEVICE OFFLINE
    # -----------------------------------

    if status == "offline":
        return {
            "action": "VERIFY_CONNECTIVITY",
            "title": "Verify device connectivity",
            "reason": "The device is currently unreachable.",
            "risk": "LOW",
            "requires_approval": False,
            "automatic_execution": False,
            "suggested_commands": [
                "show ip interface brief",
                "show interfaces",
                "show ip route"
            ]
        }

    # -----------------------------------
    # VERY HIGH LATENCY
    # -----------------------------------

    if latency is not None and latency >= 200:
        return {
            "action": "INVESTIGATE_CONGESTION",
            "title": "Investigate severe network congestion",
            "reason": f"Current latency is {latency} ms.",
            "risk": "LOW",
            "requires_approval": False,
            "automatic_execution": False,
            "suggested_commands": [
                "show interfaces",
                "show ip route"
            ]
        }

    # -----------------------------------
    # HIGH LATENCY
    # -----------------------------------

    if latency is not None and latency >= 100:
        return {
            "action": "CHECK_PERFORMANCE",
            "title": "Check network performance",
            "reason": f"High latency of {latency} ms was detected.",
            "risk": "LOW",
            "requires_approval": False,
            "automatic_execution": False,
            "suggested_commands": [
                "show interfaces"
            ]
        }

    # -----------------------------------
    # CRITICAL ALERT
    # -----------------------------------

    if critical_alerts > 0:
        return {
            "action": "INVESTIGATE_CRITICAL_ALERT",
            "title": "Investigate critical incident",
            "reason": (
                f"{critical_alerts} critical alert(s) remain open."
            ),
            "risk": "LOW",
            "requires_approval": False,
            "automatic_execution": False,
            "suggested_commands": [
                "show ip interface brief",
                "show interfaces",
                "show ip route"
            ]
        }

    # -----------------------------------
    # WARNING ALERT
    # -----------------------------------

    if warning_alerts > 0:
        return {
            "action": "INVESTIGATE_WARNING",
            "title": "Investigate warning condition",
            "reason": (
                f"{warning_alerts} warning alert(s) remain open."
            ),
            "risk": "LOW",
            "requires_approval": False,
            "automatic_execution": False,
            "suggested_commands": [
                "show interfaces"
            ]
        }

    # -----------------------------------
    # HEALTHY DEVICE
    # -----------------------------------

    return {
        "action": "NONE",
        "title": "No remediation required",
        "reason": "No active network fault requires remediation.",
        "risk": "NONE",
        "requires_approval": False,
        "automatic_execution": False,
        "suggested_commands": []
    }