def generate_troubleshooting_plan(
    action,
    status,
    latency=None,
    configuration_changed=False
):
    action = (action or "").upper()
    status = (status or "unknown").lower()

    steps = []

    # -----------------------------------
    # CONFIGURATION-RELATED ISSUE
    # -----------------------------------

    if action == "REVIEW_CONFIG_DIFF":

        steps = [
            {
                "step": 1,
                "title": "Review configuration difference",
                "type": "DIAGNOSTIC",
                "instruction": (
                    "Compare the latest configuration backup "
                    "with the previous known configuration."
                ),
                "command": None
            },
            {
                "step": 2,
                "title": "Check interface status",
                "type": "COMMAND",
                "instruction": (
                    "Verify whether any important interface is "
                    "down or administratively disabled."
                ),
                "command": "show ip interface brief"
            },
            {
                "step": 3,
                "title": "Inspect running configuration",
                "type": "COMMAND",
                "instruction": (
                    "Review the active device configuration for "
                    "unexpected changes."
                ),
                "command": "show running-config"
            },
            {
                "step": 4,
                "title": "Compare startup configuration",
                "type": "COMMAND",
                "instruction": (
                    "Compare startup configuration with the "
                    "currently running configuration."
                ),
                "command": "show startup-config"
            },
            {
                "step": 5,
                "title": "Verify network connectivity",
                "type": "VERIFICATION",
                "instruction": (
                    "Check whether the device is reachable and "
                    "network connectivity has returned to normal."
                ),
                "command": None
            }
        ]

    # -----------------------------------
    # OFFLINE DEVICE
    # -----------------------------------

    elif action == "VERIFY_CONNECTIVITY":

        steps = [
            {
                "step": 1,
                "title": "Check physical connectivity",
                "type": "MANUAL",
                "instruction": (
                    "Verify that the device is powered on and "
                    "network cables are connected."
                ),
                "command": None
            },
            {
                "step": 2,
                "title": "Test reachability",
                "type": "DIAGNOSTIC",
                "instruction": "Ping the device IP address.",
                "command": None
            },
            {
                "step": 3,
                "title": "Check interface status",
                "type": "COMMAND",
                "instruction": (
                    "Check whether required interfaces are up."
                ),
                "command": "show ip interface brief"
            },
            {
                "step": 4,
                "title": "Check routing",
                "type": "COMMAND",
                "instruction": (
                    "Inspect the routing table for missing "
                    "or incorrect routes."
                ),
                "command": "show ip route"
            }
        ]

    # -----------------------------------
    # PERFORMANCE ISSUE
    # -----------------------------------

    elif action in (
        "CHECK_PERFORMANCE",
        "INVESTIGATE_CONGESTION"
    ):

        steps = [
            {
                "step": 1,
                "title": "Review latency history",
                "type": "DIAGNOSTIC",
                "instruction": (
                    "Review recent latency measurements and "
                    "identify when degradation started."
                ),
                "command": None
            },
            {
                "step": 2,
                "title": "Inspect interfaces",
                "type": "COMMAND",
                "instruction": (
                    "Check interface utilization, errors and drops."
                ),
                "command": "show interfaces"
            },
            {
                "step": 3,
                "title": "Inspect routing",
                "type": "COMMAND",
                "instruction": (
                    "Check whether routing changes may be causing "
                    "a slower network path."
                ),
                "command": "show ip route"
            },
            {
                "step": 4,
                "title": "Verify latency",
                "type": "VERIFICATION",
                "instruction": (
                    "Measure latency again and confirm whether "
                    "performance returned to normal."
                ),
                "command": None
            }
        ]

    # -----------------------------------
    # GENERAL CRITICAL/WARNING ISSUE
    # -----------------------------------

    else:

        steps = [
            {
                "step": 1,
                "title": "Review active alerts",
                "type": "DIAGNOSTIC",
                "instruction": (
                    "Review the active incidents associated "
                    "with this device."
                ),
                "command": None
            },
            {
                "step": 2,
                "title": "Check interface status",
                "type": "COMMAND",
                "instruction": (
                    "Inspect the current interface state."
                ),
                "command": "show ip interface brief"
            },
            {
                "step": 3,
                "title": "Verify device health",
                "type": "VERIFICATION",
                "instruction": (
                    "Recheck device status, latency and alerts."
                ),
                "command": None
            }
        ]

    return {
        "action": action,
        "device_status": status,
        "configuration_changed": configuration_changed,
        "total_steps": len(steps),
        "steps": steps
    }