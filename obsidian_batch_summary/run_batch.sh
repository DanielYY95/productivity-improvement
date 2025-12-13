#!/bin/bash

# 스크립트가 위치한 디렉토리로 이동
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# .env 파일 확인
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Copying from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example. Please edit it with your configuration."
    else
        echo "❌ Error: .env.example not found."
        exit 1
    fi
fi

# 필요한 패키지 설치 확인 (간단한 체크)
if ! python3 -c "import openai, dotenv" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install openai python-dotenv
fi

# Python 스크립트 실행
echo "🚀 Starting Obsidian Batch Processor..."
python3 obsidian_batch.py
