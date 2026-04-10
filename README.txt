项目名称: fastfn
仓库地址: https://github.com/Hana-ame/fastfn.git
本地路径: C:\workplace\fastfn

项目概述:
本项目 fastfn 是一个基于 Python 的异步处理框架/工具集，主要包含以下核心模块:

主模块 (main.py): 程序入口，负责初始化和调度。

中间件模块 (middleware.py): 处理请求/响应的拦截、日志或鉴权。
  主要类: UploadBlockMiddleware

进程管理模块 (process_manager.py): 管理子进程、异步任务或并发控制。
  主要函数: start_runner

常量定义模块 (consts.py): 存放全局常量、配置项或枚举值。

功能特性 (来自 FEATURES.md):
FastFN 功能说明

FastFN 是一个基于 FastAPI 的轻量级函数即服务（FaaS）框架，允许用户上传 Python 函数并通过 HTTP 调用，同时提供 Markdown 代码块执行能力。

核心功能

1. 函数上传与管理
- 端点：PUT /fastfn/{folder}/{filename}
- 要求：
  - 文件必须以 .py 结尾，存放于 functions/{folder}/ 下。
  - 代码必须包含 main(data) 函数（支持同步/异步），并可选包含 testCases 列表用于自测。
- 行为：
  - 上传时自动运行 testCases 验证函数正确性。
  - 验证通过后，启动独立子进程（基于 runner.py）并保持常驻，实现预热。
  - 若测试失败或语法错误，文件将被删除，子进程终止。

2. 函数调用
- 端点：POST /fastfn/{folder}/{filename}
- 请求体：{"data": <任意 JSON 类型>}
- 响应：{"success": true/false, "result": <函数返回值>} 或包含错误信息。
- 机制：请求通过 process_manager 路由到对应函数的常驻子进程，子进程执行 main(data) 并返回结果。

3. 进程生命周期管理
- 空闲回收：子进程若 10 分钟无调用则自动终止，防止资源浪费。
- 最大并发限制：默认最多同时运行 100 个函数进程，超出时强制回收最久未使用的进程。
- 优雅关闭：FastAPI 应用退出时，所有子进程被安全终止。

4. Markdown 代码块执行
- 端点：POST /process
- 请求体示例：
  ``json
  {
    "text": "包含代码块的 Markdown 文本",
    "operation": "execute_markdown",
    "cwd": "可选，执行时的工作目录"
  }
  `
- 功能：
  - 自动识别并执行 Markdown 中的  ``bash  或  `python  代码块。
  - 执行结果以  `stdout  和  `stderr  块形式追加到原文档中。
- 安全限制：
  - Bash 命令默认仅允许白名单指令（如 echo, ls, pwd），可通过环境变量 ALLOW_CODE_EXECUTION 放宽。
  - 超时保护：Bash 180 秒，Python 10 秒。

5. 其他文本处理操作
/process 端点也支持简单文本操作：
- reverse：反转字符串
- uppercase / lowercase：大小写转换
- count：统计行数与字符数
- trim：去除首尾空白
- bash：直接执行一段 Bash 代码（受安全限制）

目录结构

fastfn/
├── main.py               # FastAPI 应用入口
├── process_manager.py    # 子进程池管理
├── runner.py             # 子进程执行器（动态加载用户代码）
├── consts.py             # 常量与辅助函数
├── middleware.py         # 上传功能开关中间件
├── routers/              # 路由模块
│   ├── upload.py
│   ├── call.py
│   └── process.py
├── functions/            # 用户上传的函数存储目录（运行时生成）
├── game/                 # 棋类游戏逻辑（独立功能）
├── repo/                 # 仓库缓存管理
└── test/                 # 测试脚本

快速开始
1. 安装依赖：pip install -r requirements.txt
2. 启动服务：python main.py
3. 上传示例函数：
   ``bash
   curl -X PUT http://localhost:8000/fastfn/math/add.py -F "file=@add.py"
   `
4. 调用函数：
   `bash
   curl -X POST http://localhost:8000/fastfn/math/add.py \
        -H "Content-Type: application/json" \
        -d '{"data": {"a": 1, "b": 2}}'
   `

注意事项
- 上传的函数在独立子进程中运行，与主服务隔离，但需注意用户代码的恶意行为（如无限循环）。超时机制可缓解部分风险。
- 生产环境建议将 ALLOW_CODE_EXECUTION 设为 false` 或置于反向代理后加强访问控制。

主要目录结构:
  目录: __pycache__, functions, game, repo, routers, test
  Python文件: consts.py, main.py, middleware.py, process_manager.py, runner.py
  其他重要文件: FEATURES.md, cookies.txt, gemini_3.1_flash.sh, gemini_3_flash.sh, gemma_26ba4b.sh, gemma_31b.sh, llm_test_1775746771.txt, my_state.txt

推测第三方依赖: fastapi, fastapi.middleware.cors, fastapi.responses, game, middleware, process_manager, repo, routers, starlette.middleware.base, uvicorn

使用方式:
  运行主程序: python main.py
  运行测试: pytest (如果存在测试用例)

注意: 此文件为纯文本格式，禁止使用 Markdown 语法。
