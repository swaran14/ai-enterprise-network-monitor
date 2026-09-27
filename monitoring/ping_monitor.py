import platform
import re
import subprocess


def ping_device(ip_address: str):
    """
    Ping a network device and return its status and latency.
    """

    system = platform.system().lower()

    if system == "windows":
        command = ["ping", "-n", "1", "-w", "1000", ip_address]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip_address]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3
        )

        if result.returncode == 0:

            latency = None

            match = re.search(
                r"time[=<]\s*(\d+)\s*ms",
                result.stdout,
                re.IGNORECASE
            )

            if match:
                latency = float(match.group(1))

            return {
                "status": "online",
                "latency": latency
            }

        return {
            "status": "offline",
            "latency": None
        }

    except Exception:
        return {
            "status": "offline",
            "latency": None
        }