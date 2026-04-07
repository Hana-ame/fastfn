from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
import subprocess
import tempfile
import os
import hashlib
from pathlib import Path

# app = FastAPI(title="Git Repo Explorer Service")
router = APIRouter()

# 缓存目录
CACHE_DIR = Path(__file__).parent / "repo_cache"
CACHE_DIR.mkdir(exist_ok=True)


def get_cache_key(repo_url: str, include_content: bool) -> str:
    """根据仓库URL和参数生成缓存文件名"""
    key = f"{repo_url}_{include_content}"
    hash_key = hashlib.md5(key.encode()).hexdigest()
    return f"repo_{hash_key}.txt"


def get_cache_path(repo_url: str, include_content: bool) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / get_cache_key(repo_url, include_content)


def save_to_cache(content: str, repo_url: str, include_content: bool) -> Path:
    """将内容保存到缓存文件"""
    cache_path = get_cache_path(repo_url, include_content)
    with open(cache_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return cache_path


def load_from_cache(repo_url: str, include_content: bool) -> str | None:
    """从缓存文件读取内容"""
    cache_path = get_cache_path(repo_url, include_content)
    if cache_path.exists():
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def clone_repo(repo_url: str, temp_dir: str) -> str:
    """克隆 Git 仓库到临时目录"""
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    clone_path = os.path.join(temp_dir, repo_name)
    
    result = subprocess.run(
        ['git', 'clone', '--depth', '1', repo_url, clone_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Failed to clone repo: {result.stderr}")
    
    return clone_path


def get_directory_structure(path: str, prefix: str = "") -> str:
    """递归获取目录结构并以树形格式返回"""
    result = []
    path_obj = Path(path)
    
    # 忽略 .git 目录
    if '.git' in path:
        return ""
    
    items = sorted(path_obj.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        
        if item.is_dir():
            result.append(f"{prefix}{connector}{item.name}/")
            extension = "    " if is_last else "│   "
            result.append(get_directory_structure(str(item), prefix + extension))
        else:
            result.append(f"{prefix}{connector}{item.name}")
    
    return "\n".join(filter(None, result))


def read_file_content(file_path: str) -> str:
    """读取文件内容，尝试多种编码"""
    encodings = ['utf-8', 'gbk', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    
    with open(file_path, 'rb') as f:
        return f.read().decode('utf-8', errors='ignore')


def get_all_files_content(path: str, base_path: str) -> str:
    """获取所有文件的内容"""
    result = []
    path_obj = Path(path)
    
    # 忽略 .git 目录和二进制文件
    ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env'}
    ignore_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.dat', '.db', '.json'}
    
    for item in sorted(path_obj.rglob('*')):
        if any(ignore_dir in str(item) for ignore_dir in ignore_dirs):
            continue
        
        if item.is_file():
            if item.suffix.lower() in ignore_extensions:
                continue
            
            try:
                relative_path = item.relative_to(base_path)
                content = read_file_content(str(item))
                
                result.append(f"{'='*60}")
                result.append(f"FILE: {relative_path}")
                result.append(f"{'='*60}")
                result.append(content)
                result.append("")
            except Exception:
                continue
    
    return "\n".join(result)


@router.get("/", response_class=PlainTextResponse)
async def get_repo_content(
    url: str = Query(..., description="Git repository URL"),
    include_content: bool = Query(True, description="Include file contents"),
    skip_bytes: int = Query(0, description="Skip the first N bytes of output", ge=0),
    use_cache: bool = Query(True, description="Use cached result if available")
):
    """
    获取 Git 仓库的目录结构和文件内容
    
    - **url**: Git 仓库地址（必需）
    - **include_content**: 是否包含文件内容（默认为 True）
    - **skip_bytes**: 跳过输出文本最开始的 N 个字节（默认为 0，即不跳过）
    - **use_cache**: 是否使用缓存（默认为 True）
    """
    
    # 尝试从缓存读取
    if use_cache:
        cached_content = load_from_cache(url, include_content)
        if cached_content is not None:
            if skip_bytes > 0:
                return cached_content[skip_bytes:]
            return cached_content
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            repo_path = clone_repo(url, temp_dir)
            
            output_lines = []
            output_lines.append(f"REPOSITORY: {url}")
            output_lines.append(f"{'='*60}")
            output_lines.append("")
            
            # 目录结构
            output_lines.append("DIRECTORY STRUCTURE:")
            output_lines.append(f"{'='*60}")
            output_lines.append(repo_path.split('/')[-1] + "/")
            structure = get_directory_structure(repo_path)
            if structure:
                output_lines.append(structure)
            output_lines.append("")
            
            # 文件内容
            if include_content:
                output_lines.append("FILE CONTENTS:")
                output_lines.append(f"{'='*60}")
                files_content = get_all_files_content(repo_path, repo_path)
                output_lines.append(files_content)
            
            full_output = "\n".join(output_lines)
            
            # 保存到缓存
            save_to_cache(full_output, url, include_content)
            
            # 跳过最开始的 skip_bytes 个字节
            if skip_bytes > 0:
                full_output = full_output[skip_bytes:]
            
            return full_output
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {str(e)})")


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "git-repo-explorer"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
