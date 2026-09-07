# MerchantOS Universal Platform Launcher
import os
import sys
import time
import subprocess
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PROCS = []

# Load environment variables
sys.path.insert(0, ROOT)
try:
    from src.config import HOST, PORT_HOME, PORT_AGENT1, PORT_AGENT2, PORT_AGENT3
except Exception:
    HOST = os.getenv("MERCHANTOS_HOST", "localhost")
    PORT_HOME = int(os.getenv("PORT_HOME", "8501"))
    PORT_AGENT1 = int(os.getenv("PORT_AGENT1", "8502"))
    PORT_AGENT2 = int(os.getenv("PORT_AGENT2", "8503"))
    PORT_AGENT3 = int(os.getenv("PORT_AGENT3", "8504"))

def launch(script, port, name):
    print(f"[*] Starting {name} on port {port}...")
    cmd = [sys.executable, "-m", "streamlit", "run", script, "--server.port", str(port), "--server.headless", "true"]
    env = dict(os.environ, PYTHONPATH=ROOT)
    p = subprocess.Popen(cmd, cwd=ROOT, env=env)
    PROCS.append((name, p))
    return p

def main():
    print("=" * 60)
    print("  MerchantOS: Multi-Agent Platform Launcher")
    print("=" * 60)
    services = [
        ("home.py", PORT_HOME, "Home Command Center"),
        ("Agent1/app.py", PORT_AGENT1, "Agent 1: KYC Copilot"),
        ("Agent2/app.py", PORT_AGENT2, "Agent 2: Reconciliation Copilot"),
        ("Agent3/app.py", PORT_AGENT3, "Agent 3: Escalation Copilot"),
    ]
    for s, p, n in services:
        launch(s, p, n)
        time.sleep(1.2)
    print("-" * 60)
    print(f"All 4 services are running on host: {HOST}!")
    print(f"Command Center: http://{HOST}:{PORT_HOME}")
    print("Opening browser...")
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT_HOME}")
    print("Press Ctrl+C to stop all services.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        for _, p in PROCS:
            try:
                p.terminate()
            except Exception:
                pass
        print("All services stopped.")

if __name__ == "__main__":
    main()
