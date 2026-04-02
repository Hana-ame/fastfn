# process_manager.py
# 本模块负责管理每个用户函数的常驻子进程（runner.py）
# 它维护进程的创建、调用、空闲回收和关闭，避免内存无限增长

import asyncio
import subprocess
import sys
import json
import time
from pathlib import Path

# ==================== 全局数据结构 ====================
# 存储每个函数的信息，key 为 "folder/filename"（不含 .py 后缀）
# 每个值是一个字典，包含：
#   - proc: 子进程的 Popen 对象
#   - last_used: 最后一次被调用的时间戳（浮点数，秒）
#   - code_path: 该函数对应的 code.py 文件路径
processes = {}

# ==================== 配置参数 ====================
IDLE_TIMEOUT = 600      # 空闲超时（秒），10分钟无调用则终止进程
MAX_FUNCTIONS = 100     # 最大同时运行的函数数量（防止内存爆炸）

# ==================== 子进程启动 ====================
def start_runner(code_path: Path) -> subprocess.Popen:
    """
    启动一个新的 runner.py 子进程，该进程会常驻并加载用户代码。
    子进程通过 stdin 接收 JSON 请求，通过 stdout 返回 JSON 响应。
    """
    runner_script = Path(__file__).parent / "runner.py"   # runner.py 的路径
    return subprocess.Popen(
        [sys.executable, str(runner_script), str(code_path)],  # 命令行参数
        stdin=subprocess.PIPE,   # 我们将向它写入数据
        stdout=subprocess.PIPE,  # 我们将从它读取数据
        stderr=subprocess.PIPE,  # 错误输出（可用于日志）
        text=True,               # 以文本模式（而非二进制）通信
        bufsize=1,               # 行缓冲，确保每条消息立即发送
    )
# process_manager.py 

async def test_runner(proc: subprocess.Popen, timeout=10):
    loop = asyncio.get_event_loop()
    request_line = json.dumps({"type": "test"}) + "\n"
    
    try:
        await loop.run_in_executor(None, proc.stdin.write, request_line)
        await loop.run_in_executor(None, proc.stdin.flush)
    except Exception:
        pass

    try:
        resp_line = await asyncio.wait_for(
            loop.run_in_executor(None, proc.stdout.readline),
            timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Test execution timed out (Worker forcefully killed).")

    if not resp_line:
        # 进程已关闭，获取底层错误信息！
        proc.poll()
        err_msg = proc.stderr.read().strip() if proc.stderr else "Unknown Exit"
        raise RuntimeError(f"Worker process crashed! \n[Worker Stderr]: {err_msg}")
        
    return json.loads(resp_line)


async def call_runner(proc: subprocess.Popen, data, timeout=30):
    loop = asyncio.get_event_loop()
    request_line = json.dumps({"type": "call", "data": data}) + "\n"

    try:
        await loop.run_in_executor(None, proc.stdin.write, request_line)
        await loop.run_in_executor(None, proc.stdin.flush)
    except Exception:
        pass

    try:
        resp_line = await asyncio.wait_for(
            loop.run_in_executor(None, proc.stdout.readline),
            timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Call execution timed out (Worker forcefully killed).")

    if not resp_line:
        proc.poll()
        err_msg = proc.stderr.read().strip() if proc.stderr else "Unknown Exit"
        raise RuntimeError(f"Worker process crashed! \n[Worker Stderr]: {err_msg}")
        
    return json.loads(resp_line)

# (保留 get_or_create_process, reap_idle_processes, shutdown_all_processes)
async def get_or_create_process(key: str, code_path: Path):
    """
    根据函数的唯一标识 key 获取其子进程。
    如果进程不存在或已死亡，则创建/重启。
    同时更新该函数的最后使用时间。
    """
    # 1. 检查当前活跃函数数量是否已达上限
    if key not in processes and len(processes) >= MAX_FUNCTIONS:
        await reap_idle_processes(force=True)
        if len(processes) >= MAX_FUNCTIONS:
            raise RuntimeError(f"Too many active functions (max {MAX_FUNCTIONS})")

    info = processes.get(key)
    if info is None:
        proc = start_runner(code_path)
        processes[key] = {"proc": proc, "last_used": time.time(), "code_path": code_path}
    else:
        proc = info["proc"]
        if proc.poll() is not None:
            proc = start_runner(code_path)
            processes[key]["proc"] = proc
            processes[key]["code_path"] = code_path
        processes[key]["last_used"] = time.time()
    return processes[key]["proc"]

# ==================== 空闲回收 ====================
async def reap_idle_processes(force=False):
    """
    扫描所有函数进程，终止那些超过 IDLE_TIMEOUT 未使用的进程。
    如果 force=True，则忽略空闲时间，终止所有进程（用于强制清理）。
    """
    now = time.time()
    to_remove = []
    for key, info in processes.items():
        # 判断是否需要回收：强制回收 或 空闲超时
        if force or (now - info["last_used"] > IDLE_TIMEOUT):
            proc = info["proc"]
            if proc.poll() is None:   # 进程还在运行
                proc.terminate()      # 发送 SIGTERM（Windows 下 TerminateProcess）
                try:
                    proc.wait(timeout=3)   # 等待进程退出
                except subprocess.TimeoutExpired:
                    proc.kill()            # 强制杀死
            to_remove.append(key)
    # 从全局字典中删除被回收的进程记录
    for key in to_remove:
        del processes[key]

# ==================== 应用退出时关闭所有进程 ====================
async def shutdown_all_processes():
    """
    当 FastAPI 应用关闭时，终止所有还在运行的子进程。
    """
    for info in processes.values():
        proc = info["proc"]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    processes.clear()