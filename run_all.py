import subprocess
import time
import sys
import os

def run_servers():
    print("영수증 AI 소비 분석 서비스를 시작합니다...")

    print("백엔드 서버(FastAPI)를 실행하는 중...")
    backend_process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    time.sleep(3)

    print("프론트엔드 UI(Gradio)를 실행하는 중...")
    frontend_process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print("\n모든 서버가 준비되었습니다!")
    print("- 백엔드 API: http://localhost:8000")
    print("- 프론트엔드 UI: http://localhost:7860")
    print("\n서비스를 종료하려면 이 터미널에서 Ctrl+C를 누르세요.")

    try:
        while True:
            line = backend_process.stdout.readline()
            if line:
                pass
            if backend_process.poll() is not None or frontend_process.poll() is not None:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n서버를 종료하는 중...")
        backend_process.terminate()
        frontend_process.terminate()
        print("이용해 주셔서 감사합니다!")

if __name__ == "__main__":
    run_servers()
