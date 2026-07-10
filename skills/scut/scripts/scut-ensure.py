#!/usr/bin/env python3
"""
SCUT Ensure — Self-healing SCUT listener check.

Call this from HEARTBEAT or START-HERE. It checks if the SCUT listener
is running on this machine. If not, spawns it in the background.

Usage:
  scut-ensure.py              Check and start if needed (default)
  scut-ensure.py --status     Just report status, don't start anything
  scut-ensure.py --stop       Stop the running listener

Exit codes:
  0 = listener is running (was already up or just started)
  1 = listener could not be started
  2 = config error (missing env vars)

Cross-platform: Windows + Linux. No external dependencies.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

INSTANCE = os.environ.get("OPENCLAW_INSTANCE", "")
CLAWDBOT_HOME = os.environ.get("CLAWDBOT_HOME", "")
SCUT_PORT = int(os.environ.get("SCUT_PORT", "8514"))
PID_FILE_NAME = "scut-listener.pid"


def get_home():
    if CLAWDBOT_HOME and Path(CLAWDBOT_HOME).is_dir():
        return Path(CLAWDBOT_HOME)
    for p in [
        Path("/mnt/clawdbot-home"), Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
        Path("/mnt/clawdbot-home"), Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
    ]:
        if p.is_dir():
            return p
    return None


def get_pid_file():
    """PID file lives in instance state dir — per-machine."""
    home = get_home()
    if not home or not INSTANCE:
        return None
    state_dir = home / "instances" / INSTANCE / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / PID_FILE_NAME


def is_listener_alive():
    """Check if the SCUT listener is responding on localhost."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{SCUT_PORT}/ping")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("status") == "pong"
    except Exception:
        return False


def is_pid_alive(pid):
    """Check if a process with this PID is still running."""
    try:
        if os.name == "nt":
            # Windows: tasklist check
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            return str(pid) in result.stdout
        else:
            # Linux: signal 0 check
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def read_pid():
    """Read stored PID from file."""
    pid_file = get_pid_file()
    if not pid_file or not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def write_pid(pid):
    """Write PID to file."""
    pid_file = get_pid_file()
    if pid_file:
        pid_file.write_text(str(pid))


def clear_pid():
    pid_file = get_pid_file()
    if pid_file and pid_file.exists():
        pid_file.unlink()


def start_listener():
    """Start scut.py in the background. Returns PID or None."""
    home = get_home()
    if not home:
        return None

    scut_script = home / "skills" / "scut" / "scripts" / "scut.py"
    if not scut_script.exists():
        print(f"Error: scut.py not found at {scut_script}", file=sys.stderr)
        return None

    env = os.environ.copy()
    env["OPENCLAW_INSTANCE"] = INSTANCE
    env["CLAWDBOT_HOME"] = str(home)

    try:
        if os.name == "nt":
            # Windows: use CREATE_NO_WINDOW + detached
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                [sys.executable, str(scut_script), "start"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            )
        else:
            # Linux: nohup-style detach
            proc = subprocess.Popen(
                [sys.executable, str(scut_script), "start"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return proc.pid
    except Exception as e:
        print(f"Error starting SCUT listener: {e}", file=sys.stderr)
        return None


def stop_listener():
    """Stop the running SCUT listener."""
    pid = read_pid()
    if not pid:
        # Try finding by port check
        if not is_listener_alive():
            print("SCUT listener is not running.")
            return True
        print("SCUT listener is running but PID unknown. Cannot stop automatically.", file=sys.stderr)
        return False

    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        clear_pid()
        print(f"SCUT listener stopped (PID {pid}).")
        return True
    except Exception as e:
        print(f"Error stopping SCUT listener: {e}", file=sys.stderr)
        clear_pid()
        return False


def ensure():
    """Main logic: check if running, start if not."""
    if not INSTANCE:
        print("Error: OPENCLAW_INSTANCE not set.", file=sys.stderr)
        return 2

    # Step 1: Check if listener is responding
    if is_listener_alive():
        print(f"SCUT listener: running on port {SCUT_PORT}")
        return 0

    # Step 2: Check stale PID
    old_pid = read_pid()
    if old_pid and is_pid_alive(old_pid):
        # Process exists but not responding — might be starting up, give it a moment
        print(f"SCUT process exists (PID {old_pid}) but not responding. Waiting...")
        import time
        time.sleep(2)
        if is_listener_alive():
            print(f"SCUT listener: now responding on port {SCUT_PORT}")
            return 0
        # Still dead — kill and restart
        stop_listener()

    # Step 3: Start it
    print(f"SCUT listener not running. Starting on port {SCUT_PORT}...")
    pid = start_listener()
    if not pid:
        print("Failed to start SCUT listener.", file=sys.stderr)
        return 1

    write_pid(pid)

    # Step 4: Verify it came up
    import time
    for attempt in range(5):
        time.sleep(1)
        if is_listener_alive():
            print(f"SCUT listener started (PID {pid}, port {SCUT_PORT})")
            return 0

    print(f"SCUT listener spawned (PID {pid}) but not responding after 5s. Check logs.", file=sys.stderr)
    return 1


def status():
    """Report status without changing anything."""
    alive = is_listener_alive()
    pid = read_pid()
    output = {
        "instance": INSTANCE,
        "port": SCUT_PORT,
        "listener_responding": alive,
        "stored_pid": pid,
        "pid_alive": is_pid_alive(pid) if pid else None,
    }
    print(json.dumps(output, indent=2))
    return 0 if alive else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        sys.exit(status())
    elif len(sys.argv) > 1 and sys.argv[1] == "--stop":
        sys.exit(0 if stop_listener() else 1)
    else:
        sys.exit(ensure())
