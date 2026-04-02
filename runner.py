# runner.py
import sys
import json
import importlib.util
import traceback
import asyncio
import inspect
from consts import deep_equal

async def run_logic():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: runner.py <code_path>\n")
        sys.exit(1)

    code_path = sys.argv[1]

    # 【核心性能点】：模块只在这里加载（import）一次！
    try:
        spec = importlib.util.spec_from_file_location("user_code", code_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        sys.stderr.write(f"Import Error: {traceback.format_exc()}\n")
        sys.exit(1)

    if not hasattr(module, "main"):
        sys.stderr.write("Error: No 'main' function\n")
        sys.exit(1)

    loop = asyncio.get_event_loop()

    # 循环读取 stdin，处理测试或执行请求
    while True:
        # 使用 run_in_executor 防止阻塞异步事件循环
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line: # EOF，进程关闭
            break
            
        line = line.strip()
        if not line:
            continue
            
        try:
            req = json.loads(line)
        except Exception as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}))
            sys.stdout.flush()
            continue

        req_type = req.get("type", "call")

        # 【场景 1】：上传时的测试逻辑
        if req_type == "test":
            test_cases = getattr(module, "testCases", None)
            if not isinstance(test_cases, list):
                print(json.dumps({"error": "No valid testCases array"}))
                sys.stdout.flush()
                continue

            errors =[]
            for idx, tc in enumerate(test_cases):
                if "input" not in tc or "expected" not in tc:
                    errors.append({"testCaseIndex": idx, "error": "Missing input/expected"})
                    continue
                try:
                    # 【兼容点 1】：测试用例兼容异步/同步 main 函数
                    if inspect.iscoroutinefunction(module.main):
                        actual = await module.main(tc["input"])
                    else:
                        actual = module.main(tc["input"])

                    if not deep_equal(actual, tc["expected"]):
                        errors.append({
                            "testCaseIndex": idx,
                            "input": tc["input"],
                            "expected": tc["expected"],
                            "actual": actual
                        })
                except Exception as e:
                    errors.append({"testCaseIndex": idx, "error": str(e)})

            if errors:
                print(json.dumps({"error": "Test cases failed", "details": errors}))
            else:
                print(json.dumps({"success": True}))
            sys.stdout.flush()

        # 【场景 2】：正常的 HTTP 调用逻辑
        elif req_type == "call":
            payload = req.get("data")
            try:
                # 【兼容点 2】：正式调用兼容异步/同步 main 函数
                if inspect.iscoroutinefunction(module.main):
                    result = await module.main(payload)
                else:
                    result = module.main(payload)
                    
                print(json.dumps({"result": result, "error": None}))
            except Exception:
                print(json.dumps({"result": None, "error": traceback.format_exc()}))
            sys.stdout.flush()

if __name__ == "__main__":
    # 使用 asyncio.run 启动主异步循环
    asyncio.run(run_logic())