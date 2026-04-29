#!/usr/bin/env python3
"""
一键启动 freeimage_linuxdo：同时运行后端（FastAPI, 8100）与前端（Vite, 5174）。

首次运行会自动：
  - 在 backend/.venv 创建 venv 并 pip install -r requirements.txt
  - 在 frontend/ 下 npm install（如 node_modules 不存在）
  - 若 backend/.env 不存在，会从 .env.example 拷贝一份，提醒你填写凭证

用法：
  python run.py          # 开发模式（带热重载）
  python run.py --backend-only
  python run.py --frontend-only
"""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"

BACKEND_PORT = 8100
FRONTEND_PORT = 5174


def log(tag: str, msg: str):
    print(f"\033[1;34m[{tag}]\033[0m {msg}", flush=True)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def setup_backend():
    if not (BACKEND / ".env").exists():
        if (BACKEND / ".env.example").exists():
            shutil.copy(BACKEND / ".env.example", BACKEND / ".env")
            log("setup", "已生成 backend/.env（请填写 LinuxDo Client ID/Secret 与 CATSAPI_KEY）")

    if not VENV.exists():
        log("setup", "创建 Python 虚拟环境 backend/.venv")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    py = venv_python()
    stamp = BACKEND / ".venv" / ".requirements_installed"
    req_file = BACKEND / "requirements.txt"
    need_install = not stamp.exists() or stamp.stat().st_mtime < req_file.stat().st_mtime
    if need_install:
        log("setup", "安装后端依赖 (pip install -r requirements.txt)")
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                               "-r", str(req_file)])
        stamp.write_text("ok")


def setup_frontend():
    if not (FRONTEND / "node_modules").exists():
        log("setup", "安装前端依赖 (npm install)")
        subprocess.check_call(["npm", "install"], cwd=str(FRONTEND))


def run_backend() -> subprocess.Popen:
    py = venv_python()
    log("backend", f"启动 http://127.0.0.1:{BACKEND_PORT}")
    env = os.environ.copy()
    return subprocess.Popen(
        [str(py), "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--reload"],
        cwd=str(BACKEND),
        env=env,
    )


def run_frontend() -> subprocess.Popen:
    log("frontend", f"启动 http://localhost:{FRONTEND_PORT}")
    return subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()

    procs: list[subprocess.Popen] = []

    def cleanup(*_):
        log("exit", "正在关闭子进程...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    if not args.frontend_only:
        setup_backend()
        procs.append(run_backend())

    if not args.backend_only:
        setup_frontend()
        # 给后端一点启动时间
        if not args.frontend_only:
            time.sleep(1.5)
        procs.append(run_frontend())

    # 等任何子进程退出
    while True:
        time.sleep(1)
        for p in procs:
            ret = p.poll()
            if ret is not None:
                log("exit", f"子进程 pid={p.pid} 已退出 (code={ret})")
                cleanup()


if __name__ == "__main__":
    main()
