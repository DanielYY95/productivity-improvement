import os
import time
from datetime import datetime
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv()

# --- 설정 ---
MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:27b")
TARGET_DIR = os.getenv("TARGET_DIR", "./")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "./sensitive_report.md")

extensions_str = os.getenv(
    "FILE_EXTENSIONS",
    ".yml,.yaml,.properties,.env,.json,.toml,.xml,.conf,.py,.java,.js,.ts",
)
EXTENSIONS = {ext.strip() for ext in extensions_str.split(",")}

exclude_str = os.getenv(
    "EXCLUDE_DIRS",
    "node_modules,.git,__pycache__,venv,.venv,build,dist,.idea",
)
EXCLUDE_DIRS = {d.strip() for d in exclude_str.split(",")}

SCAN_PROMPT = """당신은 민감한 정보 체크를 담당하는 보안 전문가입니다.
아래 파일 내용을 분석하여 다음과 같은 민감한 정보가 있는지 확인해주세요:
- API Key, Secret Key, Token
- 비밀번호, 인증 정보
- 개인정보 (이메일, 전화번호, 주민등록번호, 주소 등)
- 데이터베이스 접속 정보
- 하드코딩된 credential

발견된 민감 정보를 아래 형식으로 작성해주세요:
- 줄 번호와 해당 내용
- 민감 정보 유형
- 위험도 (높음/중간/낮음)

민감한 정보가 없으면 "민감한 정보가 발견되지 않았습니다."라고 작성해주세요.

[파일명]: {file_path}
[내용]:
{content}"""


def collect_files(target_dir):
    files = []
    for root, dirs, filenames in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for filename in filenames:
            if any(filename.endswith(ext) for ext in EXTENSIONS):
                files.append(os.path.join(root, filename))
    return sorted(files)


def scan_file(file_path, relative_path):
    prompt = SCAN_PROMPT.format(file_path=relative_path, content=file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError) as e:
        return None, str(e)

    prompt = SCAN_PROMPT.format(file_path=relative_path, content=content)

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"], None
    except Exception as e:
        return None, str(e)


def main():
    start_time = time.time()

    files = collect_files(TARGET_DIR)
    total = len(files)
    print(f"총 {total}개의 파일을 찾았습니다. 스캔을 시작합니다...")

    results = []
    detected_count = 0
    error_count = 0

    for idx, file_path in enumerate(files):
        relative_path = os.path.relpath(file_path, TARGET_DIR)
        print(f"[{idx + 1}/{total}] 스캔 중...: {relative_path}")

        result, error = scan_file(file_path, relative_path)

        if error:
            print(f"  !! 실패: {error}")
            with open("error_log.txt", "a", encoding="utf-8") as err_f:
                err_f.write(f"{datetime.now().isoformat()} | {file_path}: {error}\n")
            error_count += 1
            results.append((relative_path, None, error))
        else:
            has_sensitive = "민감한 정보가 발견되지 않았습니다" not in result
            if has_sensitive:
                detected_count += 1
            results.append((relative_path, result, None))

        time.sleep(2)

    elapsed = time.time() - start_time
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # --- 마크다운 리포트 작성 ---
    clean_count = total - detected_count - error_count
    lines = [
        "# 민감 정보 스캔 리포트",
        f"- 모델: {MODEL_NAME}",
        f"- 스캔 대상: {os.path.abspath(TARGET_DIR)}",
        f"- 스캔 파일 수: {total}개",
        f"- 실행 시간: {elapsed_str}",
        "",
        "---",
        "",
    ]

    for relative_path, result, error in results:
        lines.append(f"## {relative_path}")
        lines.append("")
        if error:
            lines.append(f"> 스캔 실패: {error}")
        else:
            lines.append(result)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 요약")
    lines.append(f"- 총 스캔 파일: {total}개")
    lines.append(f"- 민감 정보 발견 파일: {detected_count}개")
    lines.append(f"- 민감 정보 미발견 파일: {clean_count}개")
    if error_count:
        lines.append(f"- 스캔 실패 파일: {error_count}개")

    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_FILE)), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n스캔 완료! 리포트: {OUTPUT_FILE}")
    print(f"총 {total}개 파일 | 민감 정보 발견: {detected_count}개 | 소요 시간: {elapsed_str}")


if __name__ == "__main__":
    main()
