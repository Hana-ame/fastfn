# routers/runner.py

import sys
import json
import importlib.util
import traceback

def main():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: runner.py <code_path>\n")
        sys.exit(1)

    code_path = sys.argv[1]

    # 加载用户代码（只一次）
    spec = importlib.util.spec_from_file_location("user_code", code_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "main"):
        sys.stderr.write("Error: No 'main' function\n")
        sys.exit(1)

    # 循环处理 stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            response = {"error": f"Invalid JSON: {e}"}
            print(json.dumps(response))
            sys.stdout.flush()
            continue

        payload = req.get("data")
        try:
            result = module.main(payload)
            response = {"result": result, "error": None}
        except Exception:
            response = {"result": None, "error": traceback.format_exc()}

        print(json.dumps(response))
        sys.stdout.flush()

if __name__ == "__main__":
    main()