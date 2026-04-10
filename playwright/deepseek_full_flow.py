# playwright/deepseek_full_flow.py
r"""
完整自动化流程（优化超时处理）
1. 新建对话
2. 发送问题
3. 等待回答生成（智能轮询）
4. 保存回答到文件
"""

import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

PRESET_QUESTION = "请用中文简要介绍 Playwright 的核心功能。"

async def full_flow():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("已连接到 Edge 浏览器")
        
        if not browser.contexts:
            raise RuntimeError("没有找到浏览器上下文，请确保 Edge 已打开页面")
        context = browser.contexts[0]
        
        if not context.pages:
            page = await context.new_page()
        else:
            page = context.pages[0]
        
        # 1. 确保在 DeepSeek
        if "chat.deepseek.com" not in page.url:
            print("导航到 DeepSeek...")
            await page.goto("https://chat.deepseek.com", timeout=10000)
        else:
            print(f"当前已在 DeepSeek: {page.url}")
        
        # 2. 新建对话
        print("准备新建对话...")
        try:
            # 尝试点击侧边栏新对话按钮（优先使用文本匹配）
            new_btn = await page.wait_for_selector(
                "button:has-text('新对话'), button:has-text('New chat')",
                timeout=3000
            )
            await new_btn.click()
            print("已点击新对话按钮")
            await page.wait_for_timeout(1500)
        except PlaywrightTimeoutError:
            # 未找到按钮，导航至根路径触发新对话
            print("未找到新对话按钮，导航至首页")
            await page.goto("https://chat.deepseek.com", timeout=10000)
            await page.wait_for_load_state("networkidle")
        
        # 3. 定位输入框
        print("定位输入框...")
        input_element = await page.wait_for_selector(
            "textarea[placeholder*='Message'], textarea[placeholder*='发送消息']",
            timeout=8000
        )
        if not input_element:
            raise Exception("无法定位输入框")
        
        await input_element.fill("")
        await input_element.fill(PRESET_QUESTION)
        print(f"已填入问题: {PRESET_QUESTION}")
        
        # 发送（按 Enter）
        await input_element.press("Enter")
        print("消息已发送，等待回答...")
        
        # 4. 智能等待回答完成（优化超时）
        max_wait = 40  # 最多等待40秒
        check_interval = 2  # 每2秒检查一次
        waited = 0
        last_reply_len = 0
        stable_count = 0
        
        # 首先尝试检测停止按钮
        try:
            stop_btn = await page.wait_for_selector(
                "button:has-text('停止生成'), button:has-text('Stop generating')",
                timeout=3000
            )
            if stop_btn:
                print("检测到生成中，等待停止按钮消失...")
                await page.wait_for_selector(
                    "button:has-text('停止生成'), button:has-text('Stop generating')",
                    state="detached",
                    timeout=40000
                )
                print("停止按钮已消失，回答完成")
                # 再等1秒确保渲染
                await page.wait_for_timeout(1000)
                waited = max_wait  # 跳过轮询
        except PlaywrightTimeoutError:
            # 未出现停止按钮，采用轮询方式
            pass
        
        if waited < max_wait:
            print("采用轮询方式等待回答稳定...")
            while waited < max_wait:
                # 尝试提取当前回答文本长度
                js_len = """
                () => {
                    const msgs = document.querySelectorAll('[class*="assistant"]');
                    if (msgs.length === 0) return 0;
                    const last = msgs[msgs.length - 1];
                    return last.innerText.length;
                }
                """
                current_len = await page.evaluate(js_len)
                if current_len == last_reply_len and current_len > 20:
                    stable_count += 1
                    if stable_count >= 3:  # 连续3次长度不变且大于20字符
                        print(f"回答长度已稳定 ({current_len} 字符)")
                        break
                else:
                    stable_count = 0
                    last_reply_len = current_len
                await asyncio.sleep(check_interval)
                waited += check_interval
                print(f"  轮询中... (已等待 {waited}s, 当前长度 {current_len})")
        
        # 5. 提取回答内容
        print("提取回答内容...")
        js_extract = """
        () => {
            const selectors = [
                '.message.assistant',
                '[class*="assistant"]',
                '.chat-message.assistant'
            ];
            let messages = [];
            for (const sel of selectors) {
                messages = document.querySelectorAll(sel);
                if (messages.length > 0) break;
            }
            if (messages.length === 0) {
                messages = document.querySelectorAll('[class*="message"]');
            }
            if (messages.length > 0) {
                return messages[messages.length - 1].innerText.trim();
            }
            return "";
        }
        """
        reply_text = await page.evaluate(js_extract)
        reply_text = re.sub(r'停止生成|Stop generating', '', reply_text).strip()
        print(f"提取到回答，长度: {len(reply_text)} 字符")
        
        # 6. 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"playwright/deepseek_fullflow_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"截图已保存: {screenshot_path}")
        
        if reply_text:
            output_file = f"playwright/deepseek_fullflow_{timestamp}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"问题：{PRESET_QUESTION}\n")
                f.write(f"时间：{datetime.now().isoformat()}\n")
                f.write("-" * 50 + "\n")
                f.write("回答：\n")
                f.write(reply_text)
            print(f"问答内容已保存: {output_file}")
            print(f"回答预览:\n{reply_text[:300]}...")
        else:
            print("未提取到文本回答，请查看截图。")
        
        await browser.close()
        print("流程执行完毕！")

if __name__ == "__main__":
    asyncio.run(full_flow())
