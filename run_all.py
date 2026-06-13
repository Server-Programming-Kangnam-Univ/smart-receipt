import subprocess
import time
import sys
import os
import threading

def stream_output(process, prefix):
    """프로세스의 stdout/stderr를 실시간으로 출력한다."""
    for line in iter(process.stdout.readline, ""):
        try:
            print(f"[{prefix}] {line}", end="", flush=True)
        except UnicodeEncodeError:
            safe = line.encode("ascii", errors="replace").decode("ascii")
            print(f"[{prefix}] {safe}", end="", flush=True)

def run_servers():
    print("영수증 AI 소비 분석 서비스를 시작합니다...")

    child_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    print("\n[백엔드] FastAPI 서버를 실행하는 중...")
    backend_process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    # 파이프 버퍼가 막히지 않도록 즉시 읽기 시작
    threading.Thread(target=stream_output, args=(backend_process, "BACKEND"), daemon=True).start()

    time.sleep(5)

    if backend_process.poll() is not None:
        print("\n[ERROR] 백엔드 서버가 시작 중 종료되었습니다. 위 로그를 확인하세요.")
        sys.exit(1)

    print("[프론트엔드] Gradio UI를 실행하는 중...")
    frontend_process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    threading.Thread(target=stream_output, args=(frontend_process, "FRONTEND"), daemon=True).start()

    print("\n모든 서버가 준비되었습니다!")
    print("- 백엔드 API:    http://localhost:8000")
    print("- 프론트엔드 UI: http://localhost:7860")
    print("\n서비스를 종료하려면 이 터미널에서 Ctrl+C를 누르세요.\n")

    try:
        while True:
            b_exit = backend_process.poll()
            f_exit = frontend_process.poll()

            if b_exit is not None:
                print(f"\n[ERROR] 백엔드 서버가 종료되었습니다 (exit code: {b_exit}). 위 로그를 확인하세요.")
                frontend_process.terminate()
                sys.exit(1)

            if f_exit is not None:
                print(f"\n[ERROR] 프론트엔드 서버가 종료되었습니다 (exit code: {f_exit}). 위 로그를 확인하세요.")
                backend_process.terminate()
                sys.exit(1)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n서버를 종료하는 중...")
        backend_process.terminate()
        frontend_process.terminate()
        print("이용해 주셔서 감사합니다!")

if __name__ == "__main__":
    run_servers()
