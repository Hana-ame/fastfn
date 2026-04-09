#!/usr/bin/env python3
"""
FastAPI 测试服务器 - Markdown 代码块执行器（分离 stdout/stderr 版）
功能：使用栈状态机精确解析代码块，支持内容中的 ``` 嵌套。
      Python 执行改为创建临时文件运行。
      执行结果分离为 ```stdout 和 ```stderr 两个块。
"""

import os
import subprocess
import re
import tempfile
import sys
from typing import List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import uvicorn

# ============ 安全配置 ============
ALLOW_UNSAFE = os.getenv("ALLOW_CODE_EXECUTION", "false").lower() == "true"
ALLOW_UNSAFE = True  # 测试时强制开启

app = FastAPI(
    title="Markdown Code Executor API",
    version="4.3.0",
    description="栈方式解析，支持嵌套，分离 stdout/stderr 输出"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 数据模型 ============
class TextRequest(BaseModel):
    text: str
    operation: str = "execute_markdown"

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
def execute_bash(code: str) -> Tuple[str, str]:
    """执行 Bash 代码，返回"""
    if not ALLOW_UNSAFE:
        allowed = ("echo", "ls", "pwd", "date", "whoami", "cat ")
        if not any(code.strip().startswith(p) for p in allowed):
            return "", f"[安全限制] 仅允许: {', '.join(allowed)}"
    
    try:
        result = subprocess.run(
            code, shell=True, capture_output=True, text=True, timeout=180,
            executable="/bin/bash" if os.name != "nt" else None
        )
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", "错误：命令执行超时（180秒）"
    except Exception as e:
        return "", f"执行错误: {str(e)}"

def execute_python(code: str) -> Tuple[str, str]:
    """执行 Python 代码，返回"""
    if not ALLOW_UNSAFE:
        if "print(" not in code and "import" not in code:
            return "", "[安全限制] 仅允许 print/import"
    
    temp_file_path = None
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file_path = f.name
        
        # 执行
        result = subprocess.run(
            [sys.executable, temp_file_path], 
            capture_output=True, 
            text=True, 
            timeout=10,
            encoding='utf-8'
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        
        # 美化错误输出：去除临时文件路径，使其更整洁
        if stderr and temp_file_path:
            stderr = stderr.replace(temp_file_path, "<string>")
            
        return stdout, stderr
        
    except subprocess.TimeoutExpired:
        return "", "错误：Python 执行超时（10秒）"
    except Exception as e:
        return "", f"执行错误: {str(e)}"
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# ============ 改进的栈解析逻辑 ============
def process_markdown(markdown_text: str) -> str:
    lines = markdown_text.splitlines(keepends=False)
    output_lines = []
    stack = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # 预检查：带语言的代码块开始标记
        start_marker_match = re.match(r'^(\s*)(`{3,})(\w+)\s*$', line)

        # --- 逻辑分支1: 处理代码块结束或嵌套开始 ---
        if stack:
            current_block = stack[-1]
            min_ticks = current_block['backtick_count']
            
            # 检查结束标记
            end_match = re.match(rf'^(\s*)(`{{{min_ticks},}})\s*$', line)
            
            if end_match:
                # 如果同时匹配开始标记（带语言），视为嵌套开始
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
                    # 否则视为结束当前块
                    current_block['end_line'] = line
                    closed_block = stack.pop()
                    
                    # 处理闭合的块
                    processed_lines = _handle_closed_block(closed_block)
                    
                    # 结果回填
                    if stack:
                        stack[-1]['content_lines'].extend(processed_lines)
                    else:
                        output_lines.extend(processed_lines)
                    
                    i += 1
                    continue
            else:
                # 内容行
                current_block['content_lines'].append(line)
                i += 1
                continue

        # --- 逻辑分支2: 处理顶层代码块开始 ---
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

        # --- 逻辑分支3: 普通文本 ---
        if not stack:
            output_lines.append(line)
        else:
            stack[-1]['content_lines'].append(line)
        
        i += 1

    # 处理未闭合的块
    while stack:
        unclosed = stack.pop()
        if stack:
            stack[-1]['content_lines'].append(unclosed['start_line'])
            stack[-1]['content_lines'].extend(unclosed['content_lines'])
        else:
            output_lines.append(unclosed['start_line'])
            output_lines.extend(unclosed['content_lines'])

    return '\n'.join(output_lines)

def _handle_closed_block(block: Dict[str, Any]) -> List[str]:
    """处理闭合代码块，返回处理后的行列表"""
    result_lines = []
    
    lang = block['lang']
    indent = block['indent']
    start_line = block['start_line']
    content_lines = block['content_lines']
    end_line = block['end_line']

    # 1. 原样输出原始代码块
    result_lines.append(start_line)
    result_lines.extend(content_lines)
    result_lines.append(end_line)

    # 2. 执行代码并分离输出
    is_bash = lang in ('bash', 'sh', '')
    is_python = lang in ('python', 'py')
    
    if is_bash or is_python:
        code_content = '\n'.join(content_lines).rstrip('\n')
        
        stdout_text, stderr_text = "", ""
        
        if is_bash:
            stdout_text, stderr_text = execute_bash(code_content)
        else:
            stdout_text, stderr_text = execute_python(code_content)
        
        # 生成 stdout 块
        if stdout_text:
            result_lines.append(f"{indent}```stdout")
            for line in stdout_text.splitlines():
                result_lines.append(f"{indent}{line}")
            result_lines.append(f"{indent}```")
        
        # 生成 stderr 块
        if stderr_text:
            result_lines.append(f"{indent}```stderr")
            for line in stderr_text.splitlines():
                result_lines.append(f"{indent}{line}")
            result_lines.append(f"{indent}```")
            
        # 如果两者都为空，生成一个空的 output 提示（可选，防止完全没有反馈）
        if not stdout_text and not stderr_text:
            result_lines.append(f"{indent}```output")
            result_lines.append(f"{indent}(无输出)")
            result_lines.append(f"{indent}```")

    return result_lines

# ============ 文本处理主函数 ============
def process_text(text: str, operation: str) -> str:
    if operation == "execute_markdown":
        return process_markdown(text)
    elif operation == "reverse": return text[::-1]
    elif operation == "uppercase": return text.upper()
    elif operation == "lowercase": return text.lower()
    elif operation == "count":
        return f"行数: {len(text.splitlines())}, 字符数: {len(text)}"
    elif operation == "trim": return text.strip()
    elif operation == "bash":
        if not ALLOW_UNSAFE: return "[安全限制]"
        try:
            return subprocess.run(text, shell=True, capture_output=True, text=True, timeout=2).stdout.strip()
        except: return "执行出错"
    return text

# ============ API 路由 ============
@app.get("/")
async def root():
    return {
        "message": "Markdown Code Executor API (Stack Parser)",
        "version": "4.3.0",
        "endpoints": {"POST /process": "处理 Markdown 文本"}
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/process", response_model=TextResponse)
async def process_endpoint(request: TextRequest):
    try:
        result = process_text(request.text, request.operation)
        return TextResponse(
            result=result,
            operation=request.operation,
            original_length=len(request.text),
            processed_length=len(result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")

if __name__ == "__main__":
    print("🚀 启动服务 (栈方式解析，支持嵌套，分离 stdout/stderr)")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")