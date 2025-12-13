import os
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ================= CONFIGURATION =================
# Obsidian Vault의 루트 경로 설정 (.env에서 로드)
env_vault_path = os.getenv("VAULT_PATH")
if not env_vault_path:
    # .env에 설정이 없을 경우를 대비한 기본값 (필요시 수정)
    raise ValueError("VAULT_PATH is not set in .env file.")
else:
    VAULT_PATH = Path(env_vault_path)

today_str = datetime.datetime.now().strftime("%Y.%m.%d")

# 입력 파일: 매일 작성하는 로그 파일 경로 (Inbox)
# .env에서 폴더명을 가져오거나 기본값 "daily" 사용
INBOX_DIR_NAME = os.getenv("INBOX_DIR_NAME", "daily")
INBOX_FILE = VAULT_PATH / INBOX_DIR_NAME / f"{today_str}.md"

# 출력 폴더: 주제별로 분류된 요약 파일이 저장될 경로 (Knowledge)
# .env에서 폴더명을 가져오거나 기본값 "summary" 사용
KNOWLEDGE_DIR_NAME = os.getenv("KNOWLEDGE_DIR_NAME", "summary")
KNOWLEDGE_DIR = VAULT_PATH / KNOWLEDGE_DIR_NAME

# 아카이브 파일: 처리가 완료된 원본 로그를 백업할 파일 경로
# .env에서 폴더명을 가져오거나 기본값 "daily_archive" 사용
ARCHIVE_DIR_NAME = os.getenv("ARCHIVE_DIR_NAME", "daily_archive")
ARCHIVE_FILE = VAULT_PATH / ARCHIVE_DIR_NAME / f"{today_str}_done.md"

# 사용할 AI 모델 이름 (.env에서 설정 가능, 기본값: qwen2.5:32b)
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:32b")

# OpenAI 클라이언트 초기화 (Ollama 로컬 서버 또는 OpenAI API 사용)
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "ollama"),
)
# =================================================


class ObsidianBatchProcessor:
    def __init__(self) -> None:
        self.today = datetime.datetime.now().strftime("%Y-%m-%d")

    def read_inbox(self) -> Optional[str]:
        if not INBOX_FILE.exists():
            print(f"Error: inbox missing at {INBOX_FILE}")
            return None
        text = INBOX_FILE.read_text(encoding="utf-8").strip()
        return text if text else None

    def analyze_content(self, content: str) -> List[Dict[str, Any]]:
        prompt = f"""
Analyze the following text from my daily dev log.
The log may contain multiple distinct technical topics. Please identify and separate them.

Input Text:
{content}

Requirements:
1. Return ONLY a valid JSON array.
2. Identify ALL distinct technical topics discussed in the text. Do not merge unrelated topics (e.g., separate 'Docker Networking' from 'Java Runtime' if they are distinct sections).
3. Format: [{{"topic": "TopicName", "summary": "Korean summary...", "keywords": ["tag1", "tag2"]}}]
4. TopicName should be concise and specific (e.g., "Docker_Volume_Shadowing", "Traefik_vs_Nginx", "Java_vs_Node_Runtime").
5. Summary must be in Korean. Use Markdown formatting (bullet points, bold text) for better readability. Include key takeaways, solution steps, and comparisons if present.
6. Extract 3-5 important technical keywords for each topic.
7. If no meaningful technical content, return [].
"""
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a technical documentation assistant. Respond in JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                extra_body={"options": {"num_ctx": 16384}} # Ollama context window 확장
            )
            result_text = resp.choices[0].message.content or ""
            cleaned = result_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception as e:
            print(f"API error: {e}")
            return []

    def append_to_topic_files(self, data: List[Dict[str, Any]]) -> None:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        for item in data:
            topic = (item.get("topic") or "Uncategorized").replace("/", "_")
            summary = item.get("summary") or ""
            keywords = item.get("keywords") or []

            path = KNOWLEDGE_DIR / f"{topic}.md"
            if not path.exists():
                path.write_text(f"# {topic}\n\nRunning Logs\n---\n", encoding="utf-8")
                print(f"Created new topic file: {path.name}")

            keywords_line = f"**Keywords**: {', '.join(f'`{k}`' for k in keywords)}" if keywords else ""
            append_text = f"\n### 📅 {self.today} Summary\n{keywords_line}\n\n{summary}\n"

            with path.open("a", encoding="utf-8") as f:
                f.write(append_text)
            print(f"Appended to {path.name}")

    def archive_and_clear(self, original_content: str) -> None:
        ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ARCHIVE_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n## Processed on {self.today}\n{original_content}\n\n---\n")
        INBOX_FILE.write_text("", encoding="utf-8")
        print("✅ Inbox archived and cleared.")

    def run(self) -> None:
        content = self.read_inbox()
        if not content:
            print("📭 Inbox is empty. Skipping.")
            return
        data = self.analyze_content(content)
        if data:
            self.append_to_topic_files(data)
            self.archive_and_clear(content)
            print("🎉 Batch processing completed successfully.")
        else:
            print("⚠️ No valid data extracted from AI.")


if __name__ == "__main__":
    ObsidianBatchProcessor().run()
