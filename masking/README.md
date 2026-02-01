# Spring/Spring Boot 프로젝트 민감 정보 마스킹 도구

Spring/Spring Boot 프로젝트의 설정 파일에서 민감한 정보를 자동으로 탐지하고 마스킹 처리하는 CLI 도구입니다.

## 주요 기능

- **자동 탐지**: `application.properties`, `application.yml`, `application-*.yml`, `*.env` 파일 자동 탐지
- **스마트 마스킹**: 비밀번호, API 키, 토큰, DB 접속 정보 등 민감한 정보 패턴 인식
- **Ollama LLM 연동**: 로컬 Ollama를 통한 고급 민감 정보 탐지 (gemma3:27b 등)
- **백업 기능**: 원본 파일 백업 후 마스킹 처리
- **복원 기능**: 백업 파일을 통한 원본 복원
- **리포트 생성**: 마스킹된 항목에 대한 상세 리포트 생성

## 설치

```bash
cd masking
pip install -r requirements.txt
```

## Ollama 설정 (LLM 사용 시)

```bash
# Ollama 설치 (macOS)
brew install ollama

# Ollama 서버 실행
ollama serve

# gemma3:27b 모델 다운로드
ollama pull gemma3:27b
```

## 사용법

### 기본 사용법

```bash
# 특정 프로젝트 디렉토리 마스킹
python main.py mask /path/to/spring-project

# 현재 디렉토리의 프로젝트 마스킹
python main.py mask .

# 여러 프로젝트 한번에 마스킹
python main.py mask /path/to/project1 /path/to/project2
```

### 옵션

```bash
# 백업 없이 마스킹 (주의: 원본 덮어쓰기)
python main.py mask /path/to/project --no-backup

# 미리보기 모드 (실제 파일 변경 없음)
python main.py mask /path/to/project --dry-run

# Ollama LLM 기반 고급 탐지 활성화
python main.py mask /path/to/project --use-llm

# 커스텀 마스킹 패턴 사용
python main.py mask /path/to/project --config custom_patterns.yml

# 특정 파일 패턴만 처리
python main.py mask /path/to/project --include "application-*.yml"

# 특정 파일/폴더 제외
python main.py mask /path/to/project --exclude "test/**"
```

### Ollama 모델 확인

```bash
# 사용 가능한 Ollama 모델 목록 확인
python main.py models

# 다른 서버의 모델 확인
python main.py models --endpoint http://192.168.1.100:11434
```

### 복원

```bash
# 백업에서 복원
python main.py restore /path/to/project
```

### 리포트 확인

```bash
# 마스킹 리포트 생성
python main.py report /path/to/project
```

## 마스킹 대상 패턴

### 기본 탐지 패턴

| 카테고리     | 키 패턴 예시                                                 |
| ------------ | ------------------------------------------------------------ |
| 데이터베이스 | `spring.datasource.password`, `db.password`, `jdbc.password` |
| 인증 정보    | `secret`, `api-key`, `api_key`, `token`, `credential`        |
| 암호화       | `encrypt.key`, `jwt.secret`, `aes.key`                       |
| 외부 서비스  | `aws.secret`, `cloud.key`, `oauth.secret`                    |
| 메일 서버    | `mail.password`, `smtp.password`                             |
| Redis/캐시   | `redis.password`, `cache.password`                           |

### 마스킹 결과 예시

**Before:**

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb
    username: admin
    password: MySecretPassword123!

jwt:
  secret: my-jwt-secret-key-very-long-string
```

**After:**

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb
    username: admin
    password: "***MASKED***"

jwt:
  secret: "***MASKED***"
```

## 설정 파일

`config.yml`을 통해 마스킹 동작을 커스터마이징할 수 있습니다:

```yaml
# 탐지 대상 파일 패턴
file_patterns:
  - "application.properties"
  - "application.yml"
  - "application-*.yml"
  - "application-*.properties"
  - "*.env"
  - ".env"
  - "bootstrap.yml"
  - "bootstrap.properties"

# 민감 정보 키 패턴 (정규식)
sensitive_patterns:
  - "password"
  - "secret"
  - "key"
  - "token"
  - "credential"
  - "api[-_]?key"

# 제외할 키 패턴
exclude_patterns:
  - "public[-_]?key"
  - "key[-_]?store[-_]?type"

# 마스킹 형식
mask_format: "***MASKED***"

# Ollama LLM 설정
llm:
  enabled: false
  provider: "ollama"
  endpoint: "http://localhost:11434"
  model: "gemma3:27b"
  timeout: 120
```

## Ollama LLM 연동

로컬 Ollama를 통한 고급 민감 정보 탐지를 지원합니다:

```bash
# Ollama 서버가 실행 중인지 확인
ollama list

# LLM 활성화하여 실행
python main.py mask /path/to/project --use-llm

# 환경 변수로 Ollama 설정 변경 가능
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma3:27b"
```

### 지원 모델

config.yml에서 모델을 변경할 수 있습니다:

```yaml
llm:
  model: "gemma3:27b"      # 기본 (권장)
  model: "llama3:70b"      # 더 큰 모델
  model: "mistral:latest"  # 다른 모델
```

LLM 연동 시 장점:

- 컨텍스트 기반 민감 정보 탐지
- 패턴에 정의되지 않은 민감 정보도 탐지
- 오탐지(False Positive) 감소

## 프로젝트 구조

```
masking/
├── main.py              # CLI 진입점
├── config.yml           # 기본 설정 파일
├── requirements.txt     # Python 의존성
├── README.md            # 이 문서
├── .env.example         # 환경 변수 템플릿
├── .gitignore           # Git 제외 파일 목록
├── examples/            # 테스트용 예제 파일
└── src/
    ├── __init__.py
    ├── masker.py        # 핵심 마스킹 엔진
    ├── scanner.py       # 파일 탐색 모듈
    ├── llm_client.py    # Ollama LLM 클라이언트
    └── reporter.py      # 리포트 생성기
```

## 환경 변수

`.env.example`을 `.env`로 복사하여 환경 변수를 설정할 수 있습니다:

```bash
cp .env.example .env
```

```bash
# Ollama 설정
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:27b
```

## 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스

MIT License
