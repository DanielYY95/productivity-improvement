# Night Owl Analyst 🦉

대규모 코드 분석을 위한 로컬 LLM 배치 처리 도구입니다. Gemma 3 27B와 같은 고성능 모델을 로컬(Mac M1/M2/M3 등)에서 밤새 실행하여 프로젝트의 모든 소스 코드를 분석하고 Markdown 리포트로 저장합니다.

## 📋 개요

단순한 채팅 방식이 아닌 **"배치 처리(Batch Processing) 파이프라인"**을 구축하여, 사람이 지켜보지 않아도 에이전트가 알아서 파일을 하나씩 읽고, 분석하고, 저장합니다.

- **Queue & Save**: 전체 파일 목록을 만들어 순차적으로 처리합니다.
- **Persistence**: 분석 결과는 즉시 `analysis_results` 폴더에 Markdown 파일로 저장됩니다. 이미 분석된 파일은 건너뛰어(Skip) 중단 후 재시작을 지원합니다.
- **Fail-safe**: 특정 파일에서 에러가 발생해도 전체 프로세스가 멈추지 않고 로그를 남긴 후 다음 파일로 넘어갑니다.

## 🛠 사전 준비

1. **Python 패키지 설치**

   ```bash
   pip install ollama python-dotenv
   ```

2. **Ollama 설치 및 모델 다운로드**
   Ollama가 실행 중이어야 합니다 (`ollama serve`).

   ```bash
   ollama pull gemma3:27b
   ```

3. **환경 변수 설정 (`.env`)**

   `.env.example` 파일을 복사하여 `.env` 파일을 생성하고 설정을 수정하세요.

   ```bash
   cp .env.example .env
   ```

   `.env` 파일 내용 예시:

   ```ini
   TARGET_DIR=./my-backend-project
   OUTPUT_DIR=./analysis_results
   MODEL_NAME=gemma3:27b
   FILE_EXTENSIONS=.java,.py,.js,.ts,.xml
   ```

## 🚀 실행 방법

장시간 실행되는 스크립트이므로, 맥북이 잠들거나 터미널이 종료되어도 작업이 유지되도록 하는 것이 중요합니다. 모든 명령어에는 맥북의 잠자기를 방지하는 `caffeinate -i` 옵션을 포함합니다.

### 1. tmux 사용 (가장 추천)

세션을 유지하면서 언제든 로그를 다시 확인할 수 있어 가장 안전한 방법입니다.

```bash
# 1. tmux 설치 (Homebrew 필요)
brew install tmux

# 2. 세션 생성
tmux new -s analyzer

# 3. 스크립트 실행
caffeinate -i python3 night_owl_analyst.py
```

- **세션 분리하기 (로그오프)**: `Ctrl` + `b` 를 누르고 뗀 뒤 `d` (백그라운드에서 계속 돕니다)
- **세션 다시 접속하기**: `tmux attach -t analyzer`
- **세션 종료**: 세션 내부에서 `exit` 입력

### 2. nohup 사용 (로그 파일 저장)

터미널을 아예 꺼버리고 싶고, 결과는 로그 파일로 확인하고 싶을 때 사용합니다.

```bash
nohup caffeinate -i python3 night_owl_analyst.py > running.log 2>&1 &
```

- **실시간 로그 확인**: `tail -f running.log`
- **프로세스 종료**: `ps -ef | grep night_owl_analyst.py` 로 PID 확인 후 `kill -9 [PID]`

### 3. VS Code 활용 (간편함)

VS Code 내장 터미널에서 실행합니다.

```bash
caffeinate -i python night_owl_analyst.py
```

_주의: VS Code 창을 닫으면 안 됩니다._

## 💡 하드웨어 및 환경 관리 팁

- **전원 연결**: 배터리 모드에서는 성능 제한이 걸리거나 방전될 수 있으므로 반드시 전원을 연결하세요.
- **발열 관리**: 장시간 GPU 풀로드로 인한 스로틀링을 방지하기 위해 거치대나 쿨링 팬 사용을 권장합니다.
- **다른 앱 종료**: 메모리 확보를 위해 분석 중에는 Docker, Chrome 등 무거운 앱을 종료하는 것이 좋습니다.

## 📊 결과 활용

분석이 완료되면 `analysis_results/` 폴더에 파일별 Markdown 리포트가 생성됩니다.
이 파일들은 Obsidian 등의 도구로 열어 전체 프로젝트에 대한 지식 베이스로 활용하거나, 생성된 요약본들을 다시 LLM에게 입력하여 전체 아키텍처 다이어그램을 그리는 데 사용할 수 있습니다.
