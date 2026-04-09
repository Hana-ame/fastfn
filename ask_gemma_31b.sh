#!/bin/bash

# ================= 配置区域 =================
# 建议将 API_KEY 写入 ~/.bashrc 或 ~/.zshrc，这里作为备选
API_KEY="AIzaSyB0bhloiQMZHSxcR9mJrmAOO0bj-E5CHEk"
PROXY="http://127.0.0.1:10809"
MODEL="gemma-4-31b-it"
API_URL="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}"
# ============================================

# 检查输入
if [ -z "$1" ]; then
    echo "用法: ./ask_gemma.sh \"你的问题\""
    exit 1
fi

PROMPT="$1"

# 发送请求并返回结果
# -s: 静默模式，不显示进度条
# --proxy: 使用你指定的代理
response=$(curl -s --proxy "$PROXY" \
    -H 'Content-Type: application/json' \
    -X POST \
    -d "{
      \"contents\": [{
        \"parts\":[{\"text\": \"$PROMPT\"}]
      }],
      \"tools\": [
        { \"google_search\": {} }
      ],
      \"generationConfig\": {
        \"temperature\": 0.7,
        \"maxOutputTokens\": 2048
      }
    }" "$API_URL")

# 输出结果
# 如果你安装了 jq，建议取消下面一行的注释，以获得漂亮的彩色输出
# echo "$response" | jq '.'
echo "$response"