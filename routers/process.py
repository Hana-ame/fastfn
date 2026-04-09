# routers/process.py
import os
import subprocess
import re
import tempfile
import sys
from typing import Tuple, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

# ============ 安全配置 ============
ALLOW_UNSAFE = os.getenv("ALLOW_CODE_EXECUTION", "false").lower() == "true"
ALLOW_UNSAFE = True

router = APIRouter()

# ============ 数据模型 ============
class TextRequest(BaseModel):
    text: str
    operation: str = "execute_markdown"
    cwd: str = ""  # 执行路径 (Current Working Directory)
    timeout: int = 60  # 执行超时时间（秒）

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        allowed = {"reverse", "uppercase", "lowercase", "bash", "count", "trim", "execute_markdown", "strip_output_blocks"}
        if v not in allowed:
            raise ValueError(f"不支持的操作: {v}")
        return v

class TextResponse(BaseModel):
    result: str
    operation: str
    original_length: int
    processed_length: int

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
        
        result = subprocess.run(
            [bash_exe, temp_file_path], 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            encoding='utf-8',
            cwd=run_cwd,
            env=env
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", f"错误：命令执行超时（{timeout}秒）"
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
        result = subprocess.run(
            [sys.executable, temp_file_path], 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            encoding='utf-8',
            cwd=run_cwd,
            env=env
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        
        if stderr and temp_file_path:
            stderr = stderr.replace(temp_file_path, "<string>")
            
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", f"错误：Python 执行超时（{timeout}秒）"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# ============ 栈解析逻辑（修复死循环问题） ============

def strip_output_blocks(markdown_text: str) -> str:
    """移除 Markdown 中所有 ```stdout 和 ```stderr 代码块及其内容"""
    lines = markdown_text.splitlines(keepends=True)
    result = []
    in_output_block = False
    for line in lines:
        # 检测输出块开始标记（支持任意缩进和大小写）
        if re.match(r'^\s*```(stdout|stderr)\s*$', line, re.IGNORECASE):
            in_output_block = True
            continue
        # 当处于输出块内时，遇到单独的 ``` 即结束
        if in_output_block and re.match(r'^\s*```\s*$', line):
            in_output_block = False
            continue
        if not in_output_block:
            result.append(line)
    return ''.join(result)

def process_markdown(markdown_text: str, cwd: str = "", timeout: int = 60) -> str:
    # 第一步：清理历史输出块
    markdown_text = strip_output_blocks(markdown_text)
    lines = markdown_text.splitlines(keepends=False)
    output_lines = []
    stack = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # 检查是否是开始标记
        start_match = re.match(r'^(\s*)(`{3,})(\w*)\s*$', line)
        
        if stack:
            # 当前在代码块内部，检查是否遇到结束标记
            current = stack[-1]
            min_ticks = current['backtick_count']
            # 结束标记：相同或更多的反引号，且之后没有语言标识
            end_match = re.match(rf'^(\s*)(`{{{min_ticks},}})\s*$', line)
            
            if end_match:
                # 结束当前块
                current['end_line'] = line
                closed = stack.pop()
                processed = _handle_closed_block(closed, cwd, timeout)
                if stack:
                    stack[-1]['content_lines'].extend(processed)
                else:
                    output_lines.extend(processed)
                i += 1
                
                # 注意：结束标记之后不会立即开始新块，因为同一行不能既是结束又是开始（规范上不存在）
                # 但为了防止意外，我们继续处理下一行，而不把当前行当开始标记处理。
                continue
            else:
                # 未结束，行内容加入当前块
                current['content_lines'].append(line)
                i += 1
                continue
        
        # 不在栈内，处理开始标记
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
        
        # 普通行，直接输出
        output_lines.append(line)
        i += 1

    # 处理未闭合的块（直接原样输出，不执行）
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

# ============ 文本处理主函数 ============
def process_text(text: str, operation: str, cwd: str = "", timeout: int = 60) -> str:
    if operation == "execute_markdown":
        return process_markdown(text, cwd, timeout)
    elif operation == "strip_output_blocks":
        return strip_output_blocks(text)
    elif operation == "reverse":
        return text[::-1]
    elif operation == "uppercase":
        return text.upper()
    elif operation == "lowercase":
        return text.lower()
    elif operation == "count":
        return f"行数: {len(text.splitlines())}, 字符数: {len(text)}"
    elif operation == "trim":
        return text.strip()
    elif operation == "bash":
        if not ALLOW_UNSAFE:
            return "[安全限制]"
        try:
            stdout, stderr = execute_bash(text, cwd)
            res = stdout.strip()
            if stderr:
                res += "\n[stderr]\n" + stderr.strip()
            return res.strip()
        except Exception as e:
            return f"执行出错: {e}"
    return text

# ============ 路由端点 ============
@router.post("/process", response_model=TextResponse)
async def process_endpoint(request: TextRequest):
    try:
        result = process_text(request.text, request.operation, request.cwd, request.timeout)
        return TextResponse(
            result=result,
            operation=request.operation,
            original_length=len(request.text),
            processed_length=len(result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")
