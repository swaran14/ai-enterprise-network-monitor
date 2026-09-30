import paramiko
import socket


# Only diagnostic/read-only commands are allowed initially.
ALLOWED_COMMANDS = {
    "show version",
    "show ip interface brief",
    "show interfaces",
    "show running-config",
    "show startup-config",
    "show ip route",
    "show arp",
}


def execute_ssh_command(
    host,
    username,
    password,
    command,
    port=22,
    timeout=10
):
    """
    Connect to a network device using SSH and execute
    an approved read-only diagnostic command.
    """

    command = command.strip().lower()

    # -----------------------------------------
    # SECURITY: COMMAND ALLOWLIST
    # -----------------------------------------

    if command not in ALLOWED_COMMANDS:
        return {
            "success": False,
            "error_type": "COMMAND_NOT_ALLOWED",
            "message": f"Command '{command}' is not allowed."
        }

    client = paramiko.SSHClient()

    client.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    try:

        # -----------------------------------------
        # SSH CONNECTION
        # -----------------------------------------

        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            look_for_keys=False,
            allow_agent=False
        )

        # -----------------------------------------
        # EXECUTE COMMAND
        # -----------------------------------------

        stdin, stdout, stderr = client.exec_command(
            command,
            timeout=timeout
        )

        output = stdout.read().decode(
            "utf-8",
            errors="ignore"
        )

        error_output = stderr.read().decode(
            "utf-8",
            errors="ignore"
        )

        exit_status = stdout.channel.recv_exit_status()

        return {
            "success": True,
            "host": host,
            "command": command,
            "exit_status": exit_status,
            "output": output.strip(),
            "error_output": error_output.strip()
        }

    # -----------------------------------------
    # AUTHENTICATION ERROR
    # -----------------------------------------

    except paramiko.AuthenticationException:

        return {
            "success": False,
            "error_type": "AUTHENTICATION_FAILED",
            "message": (
                f"Authentication failed for {host}."
            )
        }

    # -----------------------------------------
    # SSH PROTOCOL ERROR
    # -----------------------------------------

    except paramiko.SSHException as error:

        return {
            "success": False,
            "error_type": "SSH_ERROR",
            "message": str(error)
        }

    # -----------------------------------------
    # CONNECTION / NETWORK ERROR
    # -----------------------------------------

    except (
        socket.timeout,
        TimeoutError,
        ConnectionRefusedError,
        OSError
    ) as error:

        return {
            "success": False,
            "error_type": "CONNECTION_ERROR",
            "message": str(error)
        }

    # -----------------------------------------
    # UNEXPECTED ERROR
    # -----------------------------------------

    except Exception as error:

        return {
            "success": False,
            "error_type": "UNKNOWN_ERROR",
            "message": str(error)
        }

    finally:

        client.close()