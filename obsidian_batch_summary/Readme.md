# Obsidian Daily Log Batch Processor

## 📖 개요 (Overview)

이 프로젝트는 Obsidian의 일일 개발 로그(Daily Log)를 자동으로 정리하고 관리하기 위한 자동화 도구입니다.
매일 작성된 로그 파일을 읽어 LLM(OpenAI 또는 로컬 Ollama)을 통해 기술 주제별로 요약 및 분류하고, 해당 주제 파일에 내용을 자동으로 추가합니다. 처리가 완료된 원본 로그는 별도로 아카이빙하여 Inbox를 항상 깨끗하게 유지합니다.

이 도구는 지식 관리 프로세스를 자동화하여 수동 분류의 번거로움을 없애고, 일일 인사이트를 체계적으로 축적하여 생산성을 극대화하기 위해 개발되었습니다.

## 🚀 주요 기능 (Features)

- **자동 요약 (Automated Summarization)**: AI를 활용하여 일일 로그의 핵심 내용을 요약합니다.
- **주제별 분류 (Topic Classification)**: 기술 주제(예: Docker, React, Java 등)를 자동으로 식별하여 분류합니다.
- **키워드 추출 (Keyword Extraction)**: 나중에 쉽게 찾아볼 수 있도록 핵심 기술 용어를 추출합니다.
- **로컬 & 클라우드 지원**: OpenAI API뿐만 아니라 Ollama를 통한 로컬 LLM 구동을 지원하여 비용과 보안 측면에서 유연합니다.
- **안전한 아카이빙 (Safe Archiving)**: 데이터 유실 방지를 위해 원본 로그를 백업한 후 Inbox를 비웁니다.

## 🛠️ 기술 스택 (Tech Stack)

- **Language**: Python 3
- **AI Integration**: OpenAI API / Ollama (Local LLM)
- **Scheduling**: Crontab / Launchd (macOS)

## ⚙️ 설정 방법 (Setup)

### 1. 사전 준비

- Python 3.8 이상
- OpenAI API Key 또는 로컬에 설치된 Ollama

### 2. 설치

```bash
git clone https://github.com/yourusername/obsidian-batch-processor.git
cd obsidian-batch-processor
pip install -r requirements.txt
```

### 3. 환경 설정

프로젝트 루트에 `.env.example`을 복사하여 `.env` 파일을 생성하고 설정을 수정합니다.

```ini
# .env
OPENAI_BASE_URL=http://localhost:11434/v1  # Ollama 사용 시
OPENAI_API_KEY=ollama                       # Ollama 사용 시 (임의 값)
MODEL_NAME=qwen2.5:32b                      # 또는 gpt-4o-mini

# Obsidian Vault 경로 설정
VAULT_PATH=${YOUR_VAULT_PATH}
INBOX_DIR_NAME=daily
KNOWLEDGE_DIR_NAME=summary
ARCHIVE_DIR_NAME=daily_archive
```

## 🏃‍♂️ 실행 방법 (Usage)

### 수동 실행

```bash
./run_batch.sh
```

### 자동 실행 스케줄링 (macOS)

#### 옵션 1: Crontab (권장)

`crontab -e` 명령어로 편집기를 열고 아래 내용을 추가하여 매일 새벽 3시에 실행되도록 설정합니다.

```bash
0 3 * * * "${PROJECT_PATH}/run_batch.sh" >> "${PROJECT_PATH}/batch.log" 2>&1
```

#### 옵션 2: Launchd

시스템이 잠자기 모드에서 깨어날 때도 실행되도록 하려면 `~/Library/LaunchAgents/` 경로에 `.plist` 파일을 생성하여 등록할 수 있습니다.

## 📂 프로젝트 구조

```
.
├── obsidian_batch.py    # 메인 처리 스크립트 (Python)
├── run_batch.sh         # 실행을 위한 쉘 스크립트 래퍼
├── .env                 # 환경 설정 파일 (Git에 포함되지 않음)
├── .env.example         # 환경 설정 템플릿
└── requirements.txt     # Python 의존성 목록
```

## 🔒 개인정보 및 보안

- 이 프로젝트는 `.env` 파일을 통해 민감한 경로와 API 키를 관리합니다.
- `.env` 파일은 `.gitignore`에 포함되어 있어 실수로 공개 저장소에 업로드되는 것을 방지합니다.

---

_Note: 이 프로젝트는 개인의 생산성 향상과 업무 자동화를 위해 개발된 포트폴리오의 일부입니다._
