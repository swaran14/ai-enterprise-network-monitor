def analyze_command_output(command, output):
    command = (command or "").strip().lower()
    output = output or ""

    normalized = output.lower()

    findings = []
    severity = "INFO"
    probable_issue = None
    recommended_action = None

    # -----------------------------------
    # SHOW IP INTERFACE BRIEF
    # -----------------------------------

    if command == "show ip interface brief":

        if "administratively down" in normalized:

            severity = "CRITICAL"

            findings.append(
                "One or more interfaces are administratively down."
            )

            probable_issue = (
                "An interface may have been manually disabled."
            )

            recommended_action = (
                "Identify the required interface and verify whether "
                "it should be enabled with the no shutdown command."
            )

        elif " down " in normalized or "down/down" in normalized:

            severity = "WARNING"

            findings.append(
                "One or more interfaces appear to be down."
            )

            probable_issue = (
                "Physical connectivity or interface state may be causing the problem."
            )

            recommended_action = (
                "Check cabling, connected devices and interface status."
            )

        elif " up " in normalized:

            findings.append(
                "Interface output contains active interfaces."
            )

            probable_issue = (
                "No obvious administratively disabled interface was detected."
            )

            recommended_action = (
                "Continue with the next troubleshooting step."
            )

        else:

            severity = "WARNING"

            findings.append(
                "Interface state could not be confidently determined."
            )

            probable_issue = (
                "The command output requires manual review."
            )

            recommended_action = (
                "Review the interface output before continuing."
            )

    # -----------------------------------
    # SHOW IP ROUTE
    # -----------------------------------

    elif command == "show ip route":

        if "gateway of last resort is not set" in normalized:

            severity = "WARNING"

            findings.append(
                "No gateway of last resort is configured."
            )

            probable_issue = (
                "A missing default route may affect connectivity."
            )

            recommended_action = (
                "Verify whether the device requires a default route."
            )

        else:

            findings.append(
                "Routing information was received."
            )

            recommended_action = (
                "Review the routing entries and continue troubleshooting."
            )

    # -----------------------------------
    # SHOW INTERFACES
    # -----------------------------------

    elif command == "show interfaces":

        if "input errors" in normalized or "output errors" in normalized:

            severity = "WARNING"

            findings.append(
                "Interface statistics contain error counters."
            )

            probable_issue = (
                "Interface errors may be contributing to network degradation."
            )

            recommended_action = (
                "Inspect interface error counters, cabling and traffic load."
            )

        else:

            findings.append(
                "Interface statistics were received."
            )

            recommended_action = (
                "Review utilization and error counters."
            )

    # -----------------------------------
    # CONFIGURATION COMMANDS
    # -----------------------------------

    elif command in (
        "show running-config",
        "show startup-config"
    ):

        findings.append(
            "Configuration output was received successfully."
        )

        recommended_action = (
            "Compare the configuration with the expected known-good configuration."
        )

    # -----------------------------------
    # UNKNOWN OUTPUT TYPE
    # -----------------------------------

    else:

        severity = "WARNING"

        findings.append(
            "No specialized analyzer exists for this command."
        )

        probable_issue = (
            "Manual interpretation of the output is required."
        )

        recommended_action = (
            "Review the output manually before continuing."
        )

    return {
        "command": command,
        "severity": severity,
        "findings": findings,
        "probable_issue": probable_issue,
        "recommended_action": recommended_action
    }