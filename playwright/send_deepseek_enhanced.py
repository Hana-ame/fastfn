# playwright/send_deepseek_enhanced.py
r"""
增强版：在已打开的 DeepSeek 聊天页面中发送问题，并智能等待回复完成，提取内容保存。
请先启动调试模式的 Edge 并确保已登录 DeepSeek。
"""

import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

PRESET_QUESTION = "请用中文简要介绍 Playwright 的核心功能。"

async def send_and_capture():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("✅ 已连接到 Edge 浏览器")
        
        # 获取第一个上下文和页面
        if not browser.contexts:
            raise RuntimeError("没有找到浏览器上下文，请确保 Edge 已打开页面")
        context = browser.contexts[0]
        
        if not context.pages:
            page = await context.new_page()
            await page.goto("https://chat.deepseek.com")
        else:
            page = context.pages[0]
            if "chat.deepseek.com" not in page.url:
                await page.goto("https://chat.deepseek.com")
        
        print(f"📍 当前页面: {page.url}")
        
        # 1. 定位输入框（优先使用已验证的选择器）
        input_selectors = [
            "textarea[placeholder*='Message']",
            "textarea[placeholder*='发送消息']",
            "div[contenteditable='true']",
            "#chat-input"
        ]
        input_element = None
        for selector in input_selectors:
            try:
                input_element = await page.wait_for_selector(selector, timeout=3000)
                if input_element:
                    print(f"🔍 找到输入框: {selector}")
                    break
            except:
                continue
        
        if not input_element:
            # 保存调试信息
            await page.screenshot(path="playwright/debug_no_input.png")
            raise Exception("无法定位输入框，请检查页面结构或登录状态。")
        
        # 2. 清空可能存在的旧内容，填入问题
        await input_element.fill("")
        await input_element.fill(PRESET_QUESTION)
        print(f"📝 已填入问题: {PRESET_QUESTION}")
        
        # 3. 发送消息（优先按 Enter 键，因为之前有效）
        await input_element.press("Enter")
        print("🚀 消息已发送，等待回复生成...")
        
        # 4. 等待回复生成完毕的策略：
        #    - 等待“停止生成”按钮出现（如果有），然后等待它消失。
        #    - 如果没有该按钮，则等待一定时间后检查回复长度稳定。
        try:
            # 等待可能出现的“停止生成”按钮
            stop_btn = await page.wait_for_selector(
                "button:has-text('停止生成'), button:has-text('Stop generating')",
                timeout=5000
            )
            if stop_btn:
                print("⏳ 检测到生成中，等待完成...")
                # 等待该按钮消失，表示生成结束
                await page.wait_for_selector(
                    "button:has-text('停止生成'), button:has-text('Stop generating')",
                    state="detached",
                    timeout=60000  # 最多等待60秒
                )
                print("✅ 生成完成（停止按钮消失）")
        except PlaywrightTimeoutError:
            # 没有找到停止按钮或超时，使用备用等待策略
            print("ℹ️ 未检测到停止按钮，使用固定等待时间（20秒）")
            await page.wait_for_timeout(20000)
        
        # 额外等待2秒确保 DOM 完全渲染
        await page.wait_for_timeout(2000)
        
        # 5. 提取最新的助手回复
        # DeepSeek 的助手消息通常有特定的类名，如 .ds-markdown 或 [class*="assistant"]
        reply_selectors = [
            ".message.assistant:last-child .ds-markdown",
            ".message.assistant:last-child p",
            "[class*='assistant']:last-child .ds-markdown",
            ".chat-message.assistant:last-child .text-content",
            ".message:last-child .ds-markdown"  # 通用尝试
        ]
        
        reply_text = None
        for sel in reply_selectors:
            try:
                element = await page.wait_for_selector(sel, timeout=3000)
                if element:
                    reply_text = await element.text_content()
                    if reply_text and len(reply_text.strip()) > 10:
                        print(f"📄 提取回复成功，选择器: {sel}")
                        break
            except:
                continue
        
        if not reply_text:
            # 降级方案：尝试获取所有可能的消息容器中的文本
            all_text = await page.evaluate("""
                () => {
                    const messages = document.querySelectorAll('[class*="message"], [class*="chat-item"]');
                    if (messages.length > 0) {
                        const lastMsg = messages[messages.length - 1];
                        return lastMsg.innerText;
                    }
                    return null;
                }
            """)
            if all_text:
                reply_text = all_text
                print("ℹ️ 使用降级方案提取回复内容")
        
        # 6. 保存截图
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"playwright/deepseek_response_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"📸 截图已保存: {screenshot_path}")
        
        # 7. 保存问题和回复到文本文件
        if reply_text:
            output_file = f"playwright/deepseek_qa_{timestamp}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"问题：{PRESET_QUESTION}\n")
                f.write(f"时间：{datetime.now().isoformat()}\n")
                f.write("-" * 50 + "\n")
                f.write("回复：\n")
                f.write(reply_text)
            print(f"💾 问答内容已保存: {output_file}")
            print(f"📋 回复预览:\n{reply_text[:300]}...")
        else:
            print("⚠️ 未能提取到回复文本，请检查截图。")
        
        # 断开连接（不关闭浏览器）
        await browser.close()

if __name__ == "__main__":
    asyncio.run(send_and_capture())
