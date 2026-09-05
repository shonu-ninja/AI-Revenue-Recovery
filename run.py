from pathlib import Path
import os
import signal
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def project_python():
    if os.name == "nt":
        candidate = ROOT / "venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / "venv" / "bin" / "python"
    return str(candidate if candidate.exists() else Path(sys.executable))


def run_setup(python_executable):
    print("Initializing database...")
    subprocess.run(
        [python_executable, "init_db.py"],
        cwd=BACKEND,
        check=True,
    )

    print("Seeding demo data...")
    subprocess.run(
        [python_executable, "seed_data.py"],
        cwd=BACKEND,
        check=True,
    )


def main():
    python_executable = project_python()
    processes = []

    try:
        run_setup(python_executable)

        print("Starting backend at http://127.0.0.1:8000...")
        processes.append(
            subprocess.Popen(
                [python_executable, "-m", "uvicorn", "main:app", "--reload"],
                cwd=BACKEND,
            )
        )

        print("Starting frontend at http://127.0.0.1:5173...")
        npm_command = "npm.cmd" if os.name == "nt" else "npm"
        processes.append(
            subprocess.Popen(
                [npm_command, "run", "dev"],
                cwd=FRONTEND,
            )
        )

        print("Application is running. Press Ctrl+C to stop both servers.")
        for process in processes:
            process.wait()

    except KeyboardInterrupt:
        print("Stopping application...")
    except subprocess.CalledProcessError as error:
        print(f"Setup failed with exit code {error.returncode}.")
        raise SystemExit(error.returncode)
    finally:
        for process in processes:
            if process.poll() is None:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
        for process in processes:
            if process.poll() is None:
                process.wait()


if __name__ == "__main__":
    main()
