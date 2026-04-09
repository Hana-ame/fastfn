#!/bin/bash

# ================= 配置区域 =================
# 建议将 API_KEY 写入 ~/.bashrc 或 ~/.zshrc，这里作为备选
API_KEY="AIzaSyB0bhloiQMZHSxcR9mJrmAOO0bj-E5CHEk"
PROXY="http://127.0.0.1:10809"
MODEL="gemini-3-flash-preview"

# 构建 API URL，确保变量被正确包裹
API_URL="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}"
# ============================================

if [ -z "$1" ]; then
    echo "用法: ./ask_gemini.sh \"你的问题\""
    exit 1
fi

PROMPT="$1"

# 使用 cat 配合 变量注入来构建 JSON，避免复杂的转义错误
# 同时开启了 google_search_retrieval 工具
read -r -d '' JSON_DATA <<EOF
{
  "contents": [{
    "parts": [{
      "text": "$PROMPT"
    }]
  }],
  "generationConfig": {
    "temperature": 0.7,
    "maxOutputTokens": 2048
  }
}
EOF

# 执行请求
# -i 参数可以看到完整的 HTTP Header，方便排查错误
response=$(curl -s --proxy "$PROXY" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "$JSON_DATA")

echo "$response"