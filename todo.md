# FastFN 项目待办清单

## 🔴 高优先级
- [ ] **完善依赖管理**：创建 `requirements.txt` 并列出所有依赖（fastapi, uvicorn, pytest 等）
- [ ] **异常处理加固**：检查 `process_manager.py` 和 `runner.py` 中子进程崩溃后的恢复逻辑
- [ ] **静态文件清理**：移除项目根目录下的临时输出文件 `out.txt`
- [ ] **配置文件集中化**：将 `IDLE_TIMEOUT`、`MAX_FUNCTIONS` 等硬编码常量移至配置文件（如 `.env` 或 `config.py`）

## 🟡 中优先级
- [ ] **单元测试覆盖**：为 `routers/` 下的路由编写 pytest 用例
- [ ] **API 文档自动生成**：补充 FastAPI 路由的 `summary` 和 `description`，确保 `/docs` 可用
- [ ] **子进程日志收集**：统一收集 `runner.py` 的 stderr 输出到日志文件，便于问题排查
- [ ] **优雅关闭增强**：在 `shutdown_all_processes` 中增加超时与强制 kill 的日志记录

## 🟢 低优先级
- [ ] **代码重构**：考虑将 `process_manager.py` 中的全局字典改为类封装
- [ ] **性能监控**：添加进程池指标（活跃数、调用次数、平均耗时）的轻量级埋点
- [ ] **前端解耦检查**：确认所有静态文件引用已移除，API 均为纯 JSON 响应
- [ ] **Git 提交规范**：配置 pre-commit 钩子进行代码格式化和基础检查

---
*最后更新：2026-04-09*
