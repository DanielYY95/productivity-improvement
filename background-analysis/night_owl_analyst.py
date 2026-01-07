import os
import time
import ollama
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 구간 ---
# 환경 변수에서 설정 로드 (기본값 제공)
TARGET_DIR = os.getenv("TARGET_DIR", "./")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./analysis_results")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:27b")

# 확장자 목록 파싱
extensions_str = os.getenv("FILE_EXTENSIONS", ".java,.py,.js,.ts,.xml")
EXTENSIONS = {ext.strip() for ext in extensions_str.split(",")}
# ----------------

def analyze_code(file_path, code_content):
    prompt = f"""
    너는 시니어 백엔드 개발자야. 아래 코드를 분석해서 다음 내용을 Markdown 형식으로 정리해줘.
    1. 이 파일의 역할과 핵심 기능 (3줄 요약)
    2. 주요 클래스/함수 설명
    3. 잠재적인 개선점이나 버그 가능성
    
    [파일명]: {file_path}
    [코드]:
    {code_content}
    """
    
    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'user', 'content': prompt},
        ])
        return response['message']['content']
    except Exception as e:
        return f"Error analyzing {file_path}: {str(e)}"

def main():
    # 결과 저장 폴더 생성
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 분석할 파일 목록 수집
    files_to_process = []
    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if any(file.endswith(ext) for ext in EXTENSIONS):
                files_to_process.append(os.path.join(root, file))

    total = len(files_to_process)
    print(f"총 {total}개의 파일을 찾았습니다. 분석을 시작합니다... (밤샘 모드 🌙)")

    for idx, file_path in enumerate(files_to_process):
        relative_path = os.path.relpath(file_path, TARGET_DIR)
        safe_name = relative_path.replace("/", "_").replace("\\", "_") + ".md"
        output_path = os.path.join(OUTPUT_DIR, safe_name)

        # 이미 분석한 파일은 건너뛰기 (중단 후 재시작 지원)
        if os.path.exists(output_path):
            print(f"[{idx+1}/{total}] 이미 완료됨: {relative_path}")
            continue

        print(f"[{idx+1}/{total}] 분석 중...: {relative_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()

            # --- 여기서 Gemma에게 요청 ---
            start_time = time.time()
            result = analyze_code(relative_path, code_content)
            end_time = time.time()
            
            # 결과 저장
            with open(output_path, "w", encoding="utf-8") as f:
                header = f"# 분석 리포트: {relative_path}\n"
                header += f"- 모델: {MODEL_NAME}\n"
                header += f"- 소요 시간: {round(end_time - start_time, 2)}초\n"
                header += "---\n\n"
                f.write(header + result)
                
        except Exception as e:
            print(f"!! 실패: {relative_path} - {e}")
            with open("error_log.txt", "a") as err_f:
                err_f.write(f"{file_path}: {e}\n")

        # 발열 관리 및 꼬임 방지를 위한 짧은 휴식
        time.sleep(2) 

    print("모든 작업이 완료되었습니다! 푹 주무셨나요? ☕️")

if __name__ == "__main__":
    main()