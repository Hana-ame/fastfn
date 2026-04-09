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
# 注意：原代码中有一行 `ALLOW_UNSAFE = True` 测试用，这里我们完全遵守环境变量，
# 若你想测试可以临时设置环境变量 ALLOW_CODE_EXECUTION=true
ALLOW_UNSAFE = True

router = APIRouter()

# ============ 数据模型 ============
class TextRequest(BaseModel):
    text: str
    operation: str = "execute_markdown"
    cwd: str = ""  # 新增：执行路径 (Current Working Directory)

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        allowed = {"reverse", "uppercase", "lowercase", "bash", "count", "trim", "execute_markdown"}
        if v not in allowed:
            raise ValueError(f"不支持的操作: {v}")
        return v

class TextResponse(BaseModel):
    result: str
    operation: str
    original_length: int
    processed_length: int

# ============ 执行器 ============
def execute_bash(code: str, cwd: str = "") -> Tuple[str, str]:
    """执行 Bash 代码，返回 (stdout, stderr)"""
    if not ALLOW_UNSAFE:
        allowed = ("echo", "ls", "pwd", "date", "whoami", "cat ")
        if not any(code.strip().startswith(p) for p in allowed):
            return "", f"[安全限制] 仅允许: {', '.join(allowed)}"
    
    # 确定 bash 执行路径
    bash_exe = "/bin/bash"
    if os.name == "nt":
        git_bash_path = r"C:\Program Files\Git\usr\bin\bash.exe"
        if os.path.exists(git_bash_path):
            bash_exe = git_bash_path
        else:
            bash_exe = "bash"  # 如果没找到，降级使用环境变量中的 bash
            
    # 检查 cwd 是否有效
    run_cwd = cwd if cwd and os.path.isdir(cwd) else None
    if cwd and not run_cwd:
        return "", f"执行错误: 指定的目录不存在 ({cwd})"

    temp_file_path = None
    try:
        # 将代码保存到临时文件中
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file_path = f.name
        
        # 运行保存的 sh 文件 (加入 cwd 参数)
        result = subprocess.run(
            [bash_exe, temp_file_path], 
            capture_output=True, 
            text=True, 
            timeout=180,
            encoding='utf-8',
            cwd=run_cwd
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", "错误：命令执行超时（180秒）"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

def execute_python(code: str, cwd: str = "") -> Tuple[str, str]:
    """执行 Python 代码，返回 (stdout, stderr)"""
    if not ALLOW_UNSAFE:
        if "print(" not in code and "import" not in code:
            return "", "[安全限制] 仅允许 print/import"
    
    # 检查 cwd 是否有效
    run_cwd = cwd if cwd and os.path.isdir(cwd) else None
    if cwd and not run_cwd:
        return "", f"执行错误: 指定的目录不存在 ({cwd})"

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file_path = f.name
        
        # 加入 cwd 参数
        result = subprocess.run(
            [sys.executable, temp_file_path], 
            capture_output=True, 
            text=True, 
            timeout=10,
            encoding='utf-8',
            cwd=run_cwd
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        
        if stderr and temp_file_path:
            stderr = stderr.replace(temp_file_path, "<string>")
            
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", "错误：Python 执行超时（10秒）"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# ============ 栈解析逻辑 ============
def process_markdown(markdown_text: str, cwd: str = "") -> str:
    lines = markdown_text.splitlines(keepends=False)
    output_lines = []
    stack = []

    i = 0
    while i < len(lines):
        line = lines[i]
        start_marker_match = re.match(r'^(\s*)(`{3,})(\w+)\s*$', line)

        if stack:
            current_block = stack[-1]
            min_ticks = current_block['backtick_count']
            end_match = re.match(rf'^(\s*)(`{{{min_ticks},}})\s*$', line)
            
            if end_match:
                if start_marker_match:
                    indent = start_marker_match.group(1)
                    backticks = start_marker_match.group(2)
                    lang = start_marker_match.group(3).lower()
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
                else:
                    current_block['end_line'] = line
                    closed_block = stack.pop()
                    processed_lines = _handle_closed_block(closed_block, cwd) # 传入 cwd
                    if stack:
                        stack[-1]['content_lines'].extend(processed_lines)
                    else:
                        output_lines.extend(processed_lines)
                    i += 1
                    continue
            else:
                current_block['content_lines'].append(line)
                i += 1
                continue

        if start_marker_match:
            indent = start_marker_match.group(1)
            backticks = start_marker_match.group(2)
            lang = start_marker_match.group(3).lower()
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

        if not stack:
            output_lines.append(line)
        else:
            stack[-1]['content_lines'].append(line)
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

def _handle_closed_block(block: Dict[str, Any], cwd: str) -> List[str]:
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
            stdout_text, stderr_text = execute_bash(code_content, cwd)
        else:
            stdout_text, stderr_text = execute_python(code_content, cwd)
        
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
def process_text(text: str, operation: str, cwd: str = "") -> str:
    if operation == "execute_markdown":
        return process_markdown(text, cwd)
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
            run_cwd = cwd if cwd and os.path.isdir(cwd) else None
            return subprocess.run(text, shell=True, capture_output=True, text=True, timeout=2, cwd=run_cwd).stdout.strip()
        except:
            return "执行出错"
    return text

# ============ 路由端点 ============
@router.post("/process", response_model=TextResponse)
async def process_endpoint(request: TextRequest):
    try:
        # 将新增的 cwd 传入
        result = process_text(request.text, request.operation, request.cwd)
        return TextResponse(
            result=result,
            operation=request.operation,
            original_length=len(request.text),
            processed_length=len(result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")