import os
import subprocess
import re
import tempfile
import sys
import signal
import urllib.request
import json
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator

from consts import BASE_DIR
from process_manager import get_or_create_process, call_runner

# ============ 安全配置 ============
ALLOW_UNSAFE = os.getenv("ALLOW_CODE_EXECUTION", "false").lower() == "true"
ALLOW_UNSAFE = True

router = APIRouter()

# ============ 数据模型 ============
class FunctionCall(BaseModel):
    name: str
    arguments: str # JSON 字符串，符合 OpenAI 标准

class TextRequest(BaseModel):
    # 兼容老版本
    text: Optional[str] = None
    operation: str = "execute_markdown"
    
    # 新版键名区分
    bash: Optional[str] = None
    python: Optional[str] = None
    markdown: Optional[str] = None
    
    # --- OpenAI 兼容字段 ---
    # 1. 兼容 OpenAI function 字段 (message.function_call)
    function: Optional[FunctionCall] = None
    # 2. 兼容 OpenAI tool_call 格式 (单一对象)
    tool_call: Optional[Dict[str, Any]] = None
    # 3. 兼容 OpenAI tool_calls 列表格式
    tool_calls: Optional[List[Dict[str, Any]]] = None
    # 4. 兼容直接作为顶级字段的 FunctionCall (name + arguments)
    name: Optional[str] = None
    arguments: Optional[str] = None
    
    # 原有的自定义键名
    fncall: Optional[FunctionCall] = None
    
    cwd: str = ""  # 执行路径 (Current Working Directory)
    timeout: int = 60  # 执行超时时间（秒）

class TextResponse(BaseModel):
    result: str
    operation: str
    original_length: int
    processed_length: int


# ============ 安全的子进程执行器（防死锁） ============
def _run_cmd_with_timeout(cmd: List[str], cwd: str, timeout: int, env: Dict[str, str]) -> Tuple[str, str]:
    """安全的子进程执行函数，确保超时后清理整个进程树，防止管道死锁"""
    kwargs = {}
    if os.name == "nt":
        # Windows: 创建新进程组，以便可以通过 CTRL_BREAK 终止整个进程树
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Unix/Linux: 创建新 Session，以便可以通过 killpg 终止整个进程组
        kwargs["preexec_fn"] = os.setsid

    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        **kwargs
    )

    try:
        # 正常等待执行结束
        stdout, stderr = p.communicate(timeout=timeout)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        # 发生超时：强杀整个进程树（包括所有衍生出的子进程/孙子进程）
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
                p.kill() # 兜底逻辑
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        
        # 必须再次调用 communicate 清空和关闭管道，防止产生僵尸进程或句柄泄露
        p.communicate()
        raise


# ============ 执行器 ============
def execute_bash(code: str, cwd: str = "", timeout: int = 60) -> Tuple[str, str]:
    """执行 Bash 代码，返回 (stdout, stderr)"""
    if not ALLOW_UNSAFE:
        allowed = ("echo", "ls", "pwd", "date", "whoami", "cat ")
        if not any(code.strip().startswith(p) for p in allowed):
            return "", f"[安全限制] 仅允许: {', '.join(allowed)}"
    
    # 确定 bash 执行路径
    bash_exe = "/bin/bash"
    if os.name == "nt":
        git_bash_path = r"C:\Program Files\Git\bin\bash.exe"
        if os.path.exists(git_bash_path):
            bash_exe = git_bash_path
        else:
            fallback_path = r"C:\Program Files\Git\usr\bin\bash.exe"
            if os.path.exists(fallback_path):
                bash_exe = fallback_path
            else:
                print("not found git bash")
                bash_exe = "bash" 
            
    # 检查 cwd 是否有效
    run_cwd = cwd if cwd and os.path.isdir(cwd) else None
    if cwd and not run_cwd:
        return "", f"执行错误: 指定的目录不存在 ({cwd})"

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file_path = f.name
        
        env = os.environ.copy()
        
        # 使用安全的防死锁执行函数替代 subprocess.run
        stdout, stderr = _run_cmd_with_timeout(
            [bash_exe, temp_file_path], 
            cwd=run_cwd, 
            timeout=timeout, 
            env=env
        )
        return stdout.strip(), stderr.strip()
        
    except subprocess.TimeoutExpired:
        return "", f"错误：命令执行超时（{timeout}秒）并已强制终止。"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

def execute_python(code: str, cwd: str = "", timeout: int = 10) -> Tuple[str, str]:
    """执行 Python 代码，返回 (stdout, stderr)"""
    if not ALLOW_UNSAFE:
        if "print(" not in code and "import" not in code:
            return "", "[安全限制] 仅允许 print/import"
    
    run_cwd = cwd if cwd and os.path.isdir(cwd) else None
    if cwd and not run_cwd:
        return "", f"执行错误: 指定的目录不存在 ({cwd})"

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file_path = f.name
        
        env = os.environ.copy()
        
        # 使用安全的防死锁执行函数替代 subprocess.run
        stdout, stderr = _run_cmd_with_timeout(
            [sys.executable, temp_file_path], 
            cwd=run_cwd, 
            timeout=timeout, 
            env=env
        )
        
        stdout = stdout.strip()
        stderr = stderr.strip()
        
        if stderr and temp_file_path:
            stderr = stderr.replace(temp_file_path, "<string>")
            
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", f"错误：Python 执行超时（{timeout}秒）并已强制终止。"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# ============ 栈解析逻辑（保持不变） ============

def strip_output_blocks(markdown_text: str) -> str:
    lines = markdown_text.splitlines(keepends=True)
    result = []
    in_output_block = False
    for line in lines:
        if re.match(r'^\s*```(stdout|stderr)\s*$', line, re.IGNORECASE):
            in_output_block = True
            continue
        if in_output_block and re.match(r'^\s*```\s*$', line):
            in_output_block = False
            continue
        if not in_output_block:
            result.append(line)
    return ''.join(result)

def process_markdown(markdown_text: str, cwd: str = "", timeout: int = 60) -> str:
    markdown_text = strip_output_blocks(markdown_text)
    lines = markdown_text.splitlines(keepends=False)
    output_lines = []
    stack = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        start_match = re.match(r'^(\s*)(`{3,})(\w*)\s*$', line)
        
        if stack:
            current = stack[-1]
            min_ticks = current['backtick_count']
            end_match = re.match(rf'^(\s*)(`{{{min_ticks},}})\s*$', line)
            
            if end_match:
                current['end_line'] = line
                closed = stack.pop()
                processed = _handle_closed_block(closed, cwd, timeout)
                if stack:
                    stack[-1]['content_lines'].extend(processed)
                else:
                    output_lines.extend(processed)
                i += 1
                continue
            else:
                current['content_lines'].append(line)
                i += 1
                continue
        
        if start_match:
            indent = start_match.group(1)
            backticks = start_match.group(2)
            lang = start_match.group(3).lower()
            stack.append({
                'lang': lang,
                'indent': indent,
                'backtick_count': len(backticks),
                'start_line': line,
                'content_lines': [],
                'end_line': None
            })
            i += 1
            continue
        
        output_lines.append(line)
        i += 1

    while stack:
        unclosed = stack.pop()
        if stack:
            stack[-1]['content_lines'].append(unclosed['start_line'])
            stack[-1]['content_lines'].extend(unclosed['content_lines'])
        else:
            output_lines.append(unclosed['start_line'])
            output_lines.extend(unclosed['content_lines'])

    return '\n'.join(output_lines)

def _handle_closed_block(block: Dict[str, Any], cwd: str, timeout: int) -> List[str]:
    result_lines = []
    lang = block['lang']
    indent = block['indent']
    start_line = block['start_line']
    content_lines = block['content_lines']
    end_line = block['end_line']

    result_lines.append(start_line)
    result_lines.extend(content_lines)
    result_lines.append(end_line)

    is_bash = lang in ('bash', 'sh', '')
    is_python = lang in ('python', 'py')
    
    if is_bash or is_python:
        code_content = '\n'.join(content_lines).rstrip('\n')
        stdout_text, stderr_text = "", ""
        
        if is_bash:
            stdout_text, stderr_text = execute_bash(code_content, cwd, timeout)
        else:
            stdout_text, stderr_text = execute_python(code_content, cwd, timeout)
        
        if stdout_text:
            result_lines.append(f"{indent}```stdout")
            for line in stdout_text.splitlines():
                result_lines.append(f"{indent}{line}")
            result_lines.append(f"{indent}```")
        
        if stderr_text:
            result_lines.append(f"{indent}```stderr")
            for line in stderr_text.splitlines():
                result_lines.append(f"{indent}{line}")
            result_lines.append(f"{indent}```")
            
        if not stdout_text and not stderr_text:
            result_lines.append(f"{indent}```output")
            result_lines.append(f"{indent}(无输出)")
            result_lines.append(f"{indent}```")

    return result_lines

def try_decompress(text: str) -> str:
    import base64
    import gzip
    try:
        # Check if text is base64 encoded gzip
        if len(text) > 10 and re.match(r'^[A-Za-z0-9+/=\s]+$', text):
            data = base64.b64decode(text.strip())
            if data.startswith(b'\x1f\x8b'):
                return gzip.decompress(data).decode('utf-8')
    except Exception:
        pass
    return text

def fetch_from_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = response.read()
            if data.startswith(b'\x1f\x8b'):
                import gzip
                data = gzip.decompress(data)
            return data.decode('utf-8')
    except Exception as e:
        raise ValueError(f"无法从URL获取内容: {e}")

# ============ 文本处理主函数 ============
def process_text(text: str, operation: str, cwd: str = "", timeout: int = 60) -> str:
    if text.strip().startswith("http://") or text.strip().startswith("https://"):
        text = fetch_from_url(text.strip())
    else:
        text = try_decompress(text)

    if operation == "execute_markdown":
        return process_markdown(text, cwd, timeout)
    elif operation == "execute_python":
        stdout, stderr = execute_python(text, cwd, timeout)
        result = []
        if stdout:
            result.append(f"```stdout\n{stdout}\n```")
        if stderr:
            result.append(f"```stderr\n{stderr}\n```")
        if not stdout and not stderr:
            result.append("```output\n(无输出)\n```")
        return '\n'.join(result)
    elif operation == "execute_bash":
        stdout, stderr = execute_bash(text, cwd, timeout)
        result = []
        if stdout:
            result.append(f"```stdout\n{stdout}\n```")
        if stderr:
            result.append(f"```stderr\n{stderr}\n```")
        if not stdout and not stderr:
            result.append("```output\n(无输出)\n```")
        return '\n'.join(result)
    else:
        raise ValueError(f"不支持的操作: {operation}，仅允许 execute_markdown, execute_python, execute_bash")

async def handle_fncall(fncall: FunctionCall, cwd: str, timeout: int) -> str:
    name = fncall.name
    try:
        args = json.loads(fncall.arguments)
    except Exception:
        args = {"text": fncall.arguments} # Fallback if not valid JSON

    if name == "execute_bash":
        code = args.get("code") or args.get("command") or args.get("text") or ""
        stdout, stderr = await run_in_threadpool(execute_bash, code, cwd, timeout)
        res = []
        if stdout: res.append(f"```stdout\n{stdout}\n```")
        if stderr: res.append(f"```stderr\n{stderr}\n```")
        return "\n".join(res) if res else "```output\n(无输出)\n```"
    elif name == "execute_python":
        code = args.get("code") or args.get("python") or args.get("text") or ""
        stdout, stderr = await run_in_threadpool(execute_python, code, cwd, timeout)
        res = []
        if stdout: res.append(f"```stdout\n{stdout}\n```")
        if stderr: res.append(f"```stderr\n{stderr}\n```")
        return "\n".join(res) if res else "```output\n(无输出)\n```"
    elif name == "execute_markdown":
        text = args.get("text") or args.get("markdown") or ""
        return await run_in_threadpool(process_markdown, text, cwd, timeout)
    else:
        # 尝试调用 external functions (folder.filename)
        # 支持多种分隔符
        name_clean = name.replace(":", "/").replace(".", "/")
        if "/" in name_clean:
            folder, filename = name_clean.rsplit("/", 1)
            if not filename.endswith(".py"):
                filename += ".py"
            file_path = BASE_DIR / folder / filename
            if not file_path.exists():
                raise ValueError(f"函数 {name} 未找到 (路径: {file_path})")

            key = f"{folder}/{filename}"
            proc = await get_or_create_process(key, file_path)
            response = await call_runner(proc, args, timeout=timeout)
            if response.get("error"):
                return f"Error: {response['error']}"
            return json.dumps(response.get("result"), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"未知函数: {name}")


# ============ 路由端点 ============
@router.post("/process", response_model=TextResponse)
async def process_endpoint(request: TextRequest):
    try:
        # 1. 优先处理各种 OpenAI 风格的函数调用
        target_fn = request.fncall or request.function
        
        # 处理顶级字段 (name + arguments)
        if target_fn is None and request.name and request.arguments:
            target_fn = FunctionCall(name=request.name, arguments=request.arguments)
            
        # 处理单一 tool_call 对象
        if target_fn is None and request.tool_call:
            f_data = request.tool_call.get("function")
            if f_data and "name" in f_data and "arguments" in f_data:
                target_fn = FunctionCall(**f_data)
                
        # 处理 tool_calls 列表 (取第一个)
        if target_fn is None and request.tool_calls and len(request.tool_calls) > 0:
            f_data = request.tool_calls[0].get("function")
            if f_data and "name" in f_data and "arguments" in f_data:
                target_fn = FunctionCall(**f_data)

        if target_fn is not None:
            result = await handle_fncall(target_fn, request.cwd, request.timeout)
            return TextResponse(
                result=result,
                operation=f"fncall:{target_fn.name}",
                original_length=len(target_fn.arguments),
                processed_length=len(result)
            )

        # 2. 兼容性处理：确定需要执行的文本和操作
        if request.bash is not None:
            text = request.bash
            operation = "execute_bash"
        elif request.python is not None:
            text = request.python
            operation = "execute_python"
        elif request.markdown is not None:
            text = request.markdown
            operation = "execute_markdown"
        elif request.text is not None:
            text = request.text
            operation = request.operation
        else:
            raise ValueError("未提供有效的执行代码 (缺少 bash, python, markdown, text 或 OpenAI 风格字段)")

        # 使用 run_in_threadpool 防止阻塞
        result = await run_in_threadpool(
            process_text, 
            text, 
            operation, 
            request.cwd, 
            request.timeout
        )
        return TextResponse(
            result=result,
            operation=operation,
            original_length=len(text),
            processed_length=len(result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")
