# Sensitive Scanner

로컬 LLM(gemma3:27b)을 사용하여 프로젝트 내 민감 정보(API Key, Secret, 개인정보 등)를 탐지하고 마크다운 리포트로 출력합니다.

## 사전 요구사항

- Python 3.9+
- [Ollama](https://ollama.ai) 설치 및 `gemma3:27b` 모델 다운로드

```bash
ollama pull gemma3:27b
```

## 설치 및 실행

```bash
cd sensitive-scanner
pip install -r requirements.txt
cp .env-example .env
# .env 파일에서 TARGET_DIR을 스캔 대상 폴더로 수정
python main.py
```

## 환경변수

| 변수              | 설명             | 기본값                                                                 |
| ----------------- | ---------------- | ---------------------------------------------------------------------- |
| `MODEL_NAME`      | Ollama 모델명    | `gemma3:27b`                                                           |
| `TARGET_DIR`      | 스캔 대상 폴더   | `./`                                                                   |
| `OUTPUT_FILE`     | 리포트 출력 경로 | `./sensitive_report.md`                                                |
| `FILE_EXTENSIONS` | 스캔 대상 확장자 | `.yml,.yaml,.properties,.env,.json,.toml,.xml,.conf,.py,.java,.js,.ts` |
| `EXCLUDE_DIRS`    | 제외 디렉토리    | `node_modules,.git,__pycache__,venv,.venv,build,dist,.idea`            |

## 출력

실행 후 `sensitive_report.md`에 파일별 분석 결과와 요약이 생성됩니다.
