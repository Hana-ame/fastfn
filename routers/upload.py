# routers/upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException
import time
import asyncio

from process_manager import processes, get_or_create_process, test_runner
from consts import BASE_DIR

router = APIRouter()


@router.put("/{folder}/{filename}")
async def upload(folder: str, filename: str, file: UploadFile = File(...)):
    # 1. 安全检查
    if ".." in folder or ".." in filename or "/" in folder:
        raise HTTPException(400, "Invalid folder or filename")
    if not filename.endswith(".py"):
        raise HTTPException(400, "Only .py files")

    # 2. 读取并直接保存到目标路径（如果有错误我们会删掉它）
    content = await file.read()
    file_path = BASE_DIR / folder / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)

    key = f"{folder}/{filename}"

    # 3. 如果这个函数之前在运行，杀掉旧的 Worker
    if key in processes:
        old_proc = processes[key]["proc"]
        if old_proc.poll() is None:
            old_proc.terminate()
            old_proc.wait(timeout=3)
        del processes[key]

    try:
        # 4. 【核心】：建立全新的 Worker（文件在这里执行 import 动作）
        proc = await get_or_create_process(key, file_path)

        # 5. 向 Worker 发送指令，执行 testCases
        test_result = await test_runner(proc, timeout=5.0)

        # 如果测试不包含 success: True，说明测试报错
        if test_result.get("error"):
            raise Exception(test_result)

        # 测试成功！Worker 现在保持存活，并且已经在内存中加载了模块
        return {"message": "saved and pre-warmed", "path": str(file_path)}

    except Exception as e:
        # 6. 【回滚】：测试失败或语法错误，杀掉 Worker，清理无效文件
        if key in processes:
            err_proc = processes[key]["proc"]
            if err_proc.poll() is None:
                err_proc.terminate()
            del processes[key]

        file_path.unlink(missing_ok=True)  # 删除错误代码

        # 提取报错信息返回给用户
        if isinstance(e.args[0], dict):
            raise HTTPException(400, detail=e.args[0])
        elif isinstance(e, asyncio.TimeoutError):
            raise HTTPException(
                400, "Test execution timed out (possible infinite loop)."
            )
        else:
            raise HTTPException(
                400, detail={"error": "Worker or Code Error", "details": str(e)}
            )
