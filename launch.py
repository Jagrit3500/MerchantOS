# MerchantOS Universal Platform Launcher
import os
import sys
import time
import subprocess
import webbrowser
import socket

ROOT = os.path.dirname(os.path.abspath(__file__))
PROCS = []

# Load environment variables
sys.path.insert(0, ROOT)
from src import config


def wait_for_port(port, timeout=None):
    timeout = config.LAUNCH_READINESS_TIMEOUT if timeout is None else timeout
    deadline = time.time() + timeout
    while time.time() < deadline:
        for loopback in dict.fromkeys((config.FRONTEND_BIND_HOST, config.HOST)):
            try:
                with socket.create_connection((loopback, port), timeout=config.PORT_CHECK_TIMEOUT):
                    return True
            except OSError:
                continue
        time.sleep(config.LAUNCH_POLL_INTERVAL)
    return False


def cleanup():
    """Terminate every child and wait briefly so ports are released reliably."""
    for _, process in reversed(PROCS):
        if process.poll() is None:
            process.terminate()
    deadline = time.time() + config.LAUNCH_SHUTDOWN_TIMEOUT
    for _, process in reversed(PROCS):
        remaining = max(deadline - time.time(), 0)
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def ensure_ports_available(ports):
    occupied = [str(port) for port in ports if wait_for_port(port, timeout=config.PORT_CHECK_TIMEOUT)]
    if occupied:
        raise RuntimeError(f"These configured ports are already in use: {', '.join(occupied)}")

def launch(script, port, name):
    print(f"[*] Starting {name} on port {port}...")
    cmd = [sys.executable, "-m", "streamlit", "run", script, "--server.port", str(port), "--server.headless", "true"]
    env = dict(os.environ, PYTHONPATH=ROOT)
    p = subprocess.Popen(cmd, cwd=ROOT, env=env)
    PROCS.append((name, p))
    return p


def launch_landing():
    print(f"[*] Starting MerchantOS Landing Page on port {config.PORT_LANDING}...")
    env = dict(os.environ, PYTHONPATH=ROOT)
    process = subprocess.Popen([sys.executable, "serve_frontend.py"], cwd=ROOT, env=env)
    PROCS.append(("Landing Page", process))
    return process

def main():
    print("=" * 60)
    print("  MerchantOS: Multi-Agent Platform Launcher")
    print("=" * 60)
    services = [
        ("home.py", config.PORT_HOME, "Home Command Center"),
        ("Agent1/app.py", config.PORT_AGENT1, "Agent 1: KYC Copilot"),
        ("Agent2/app.py", config.PORT_AGENT2, "Agent 2: Reconciliation Copilot"),
        ("Agent3/app.py", config.PORT_AGENT3, "Agent 3: Escalation Copilot"),
    ]
    expected = [("Landing Page", config.PORT_LANDING)] + [(name, port) for _, port, name in services]
    try:
        ensure_ports_available(port for _, port in expected)
        launch_landing()
        for script, port, name in services:
            launch(script, port, name)
        unavailable = [name for name, port in expected if not wait_for_port(port)]
        exited = [name for name, process in PROCS if process.poll() is not None]
        if unavailable or exited:
            failed = sorted(set(unavailable + exited))
            raise RuntimeError(f"Services did not become ready: {', '.join(failed)}")
        print("-" * 60)
        print(f"Landing page and all {len(services)} workspace services are ready!")
        print(f"Website:       {config.app_urls()['landing']}")
        print(f"Command Center: {config.app_urls()['home']}")
        if config.GOOGLE_AUTH_REQUESTED and not config.GOOGLE_AUTH_CONFIGURED:
            print("Google sign-in is disabled until GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are added to .env.")
        if config.OPEN_BROWSER and "--no-browser" not in sys.argv:
            print("Opening browser...")
            webbrowser.open(config.app_urls()["landing"])
        print("Press Ctrl+C to stop all services.")
        while True:
            stopped = [name for name, process in PROCS if process.poll() is not None]
            if stopped:
                raise RuntimeError(f"Service exited unexpectedly: {', '.join(stopped)}")
            time.sleep(config.LAUNCH_MONITOR_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping services...")
    except RuntimeError as exc:
        print(f"Startup/runtime failure: {exc}", file=sys.stderr)
        return 1
    finally:
        cleanup()
    if PROCS:
        print("All services stopped.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
