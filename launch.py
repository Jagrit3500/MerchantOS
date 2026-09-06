# MerchantOS Universal Platform Launcher
import os
import sys
import time
import subprocess
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PROCS = []

def launch(script, port, name):
    print(f"[*] Starting {name} (Port {port})...")
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
        ("home.py", 8501, "Home Command Center"),
        ("Agent1/app.py", 8502, "Agent 1: KYC Copilot"),
        ("Agent2/app.py", 8503, "Agent 2: Reconciliation Copilot"),
        ("Agent3/app.py", 8504, "Agent 3: Escalation Copilot"),
    ]
    for s, p, n in services:
        launch(s, p, n)
        time.sleep(1.2)
    print("-" * 60)
    print("All 4 services are running!")
    print("Command Center: http://localhost:8501")
    print("Opening browser...")
    time.sleep(1.5)
    webbrowser.open("http://localhost:8501")
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
