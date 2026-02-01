"""
LLM API 클라이언트 모듈

Ollama LLM을 통해 민감 정보를 탐지합니다.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import requests


class LLMProvider(Enum):
    """LLM 제공자 유형"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 설정"""
    provider: LLMProvider = LLMProvider.OLLAMA
    endpoint: str = "http://localhost:11434"
    model: str = "gemma3:27b"
    api_key: Optional[str] = None
    timeout: int = 120  # Ollama는 더 긴 타임아웃 필요
    max_retries: int = 3
    prompt_template: str = ""
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'LLMConfig':
        """딕셔너리에서 LLMConfig 생성"""
        llm_config = config.get('llm', {})
        
        # provider 파싱
        provider_str = llm_config.get('provider', 'ollama').lower()
        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            provider = LLMProvider.OLLAMA
        
        return cls(
            provider=provider,
            endpoint=llm_config.get('endpoint', os.getenv('OLLAMA_HOST', 'http://localhost:11434')),
            model=llm_config.get('model', os.getenv('OLLAMA_MODEL', 'gemma3:27b')),
            api_key=os.getenv('LLM_API_KEY'),
            timeout=llm_config.get('timeout', 120),
            max_retries=llm_config.get('max_retries', 3),
            prompt_template=llm_config.get('prompt_template', '')
        )


class OllamaClient:
    """Ollama LLM 클라이언트"""
    
    DEFAULT_PROMPT_TEMPLATE = """당신은 Spring/Spring Boot 프로젝트의 보안 전문가입니다.
다음 설정 파일에서 민감한 정보(비밀번호, API 키, 토큰, 인증 정보, 암호화 키, 접속 정보 등)가 포함된 키를 찾아주세요.

설정 파일 내용:
```
{content}
```

중요: 반드시 아래 JSON 형식으로만 응답하세요. 다른 설명이나 텍스트 없이 JSON만 출력하세요.
민감한 키가 있으면:
{{"sensitive_keys": ["spring.datasource.password", "jwt.secret", ...]}}

민감한 키가 없으면:
{{"sensitive_keys": []}}"""
    
    def __init__(self, config: LLMConfig):
        """
        Args:
            config: LLM 설정
        """
        self.config = config
        self.session = requests.Session()
        self.base_url = config.endpoint.rstrip('/')
        
    def _get_prompt(self, content: str) -> str:
        """프롬프트 생성"""
        template = self.config.prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        return template.format(content=content)
    
    def _make_request(self, prompt: str) -> Dict[str, Any]:
        """Ollama API 요청 (generate 엔드포인트 사용)"""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # 결정적 응답
                "num_predict": 2000,
            }
        }
        
        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def _make_chat_request(self, prompt: str) -> Dict[str, Any]:
        """Ollama Chat API 요청 (/api/chat 엔드포인트)"""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a security expert. Always respond with valid JSON only, no explanations."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
            }
        }
        
        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def _parse_response(self, response: Dict[str, Any]) -> List[str]:
        """Ollama 응답에서 민감 키 리스트 추출"""
        try:
            # generate API 응답
            content = response.get('response', '')
            
            # chat API 응답
            if not content and 'message' in response:
                content = response.get('message', {}).get('content', '')
            
            content = content.strip()
            
            # JSON 블록 찾기
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                content = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                if end > start:
                    content = content[start:end].strip()
            
            # JSON 객체 부분만 추출
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                content = content[json_start:json_end]
            
            # JSON 파싱
            data = json.loads(content)
            return data.get('sensitive_keys', [])
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Warning: Failed to parse Ollama response: {e}")
            print(f"Response content: {response.get('response', '')[:200]}...")
            return []
    
    def detect_sensitive_keys(self, content: str) -> List[str]:
        """
        Ollama를 사용하여 민감한 키를 탐지합니다.
        
        Args:
            content: 설정 파일 내용
            
        Returns:
            민감한 키 리스트
        """
        prompt = self._get_prompt(content)
        
        for attempt in range(self.config.max_retries):
            try:
                # chat API 먼저 시도, 실패시 generate API 사용
                try:
                    response = self._make_chat_request(prompt)
                except:
                    response = self._make_request(prompt)
                    
                return self._parse_response(response)
                
            except requests.exceptions.RequestException as e:
                print(f"Warning: Ollama request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
                    
            except Exception as e:
                print(f"Warning: Unexpected error during Ollama detection: {e}")
                break
        
        return []
    
    def is_available(self) -> bool:
        """Ollama가 사용 가능한지 확인"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                # 모델이 설치되어 있는지 확인
                data = response.json()
                models = [m.get('name', '') for m in data.get('models', [])]
                model_base = self.config.model.split(':')[0]
                return any(model_base in m for m in models)
            return False
        except Exception as e:
            print(f"Warning: Cannot connect to Ollama: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """사용 가능한 모델 목록 반환"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m.get('name', '') for m in data.get('models', [])]
            return []
        except:
            return []


class OpenAICompatibleClient:
    """OpenAI 호환 API 클라이언트 (Ollama OpenAI 호환 모드 포함)"""
    
    DEFAULT_PROMPT_TEMPLATE = """다음은 Spring/Spring Boot 프로젝트의 설정 파일 내용입니다.
민감한 정보(비밀번호, API 키, 토큰, 인증 정보, 암호화 키 등)가 포함된 키를 식별해주세요.

파일 내용:
```
{content}
```

JSON 형식으로만 응답해주세요. 다른 설명 없이 JSON만 출력해주세요:
{{"sensitive_keys": ["key1", "key2", ...]}}"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.session = requests.Session()
        self.base_url = config.endpoint.rstrip('/')
        
        self.headers = {'Content-Type': 'application/json'}
        if config.api_key:
            self.headers['Authorization'] = f'Bearer {config.api_key}'
    
    def _get_prompt(self, content: str) -> str:
        template = self.config.prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        return template.format(content=content)
    
    def _make_request(self, prompt: str) -> Dict[str, Any]:
        # OpenAI 호환 엔드포인트
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a security expert. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        response = self.session.post(url, headers=self.headers, json=payload, timeout=self.config.timeout)
        response.raise_for_status()
        return response.json()
    
    def _parse_response(self, response: Dict[str, Any]) -> List[str]:
        try:
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            content = content.strip()
            
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                content = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                content = content[start:end].strip()
            
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                content = content[json_start:json_end]
            
            data = json.loads(content)
            return data.get('sensitive_keys', [])
        except Exception as e:
            print(f"Warning: Failed to parse response: {e}")
            return []
    
    def detect_sensitive_keys(self, content: str) -> List[str]:
        prompt = self._get_prompt(content)
        
        for attempt in range(self.config.max_retries):
            try:
                response = self._make_request(prompt)
                return self._parse_response(response)
            except requests.exceptions.RequestException as e:
                print(f"Warning: Request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                print(f"Warning: Unexpected error: {e}")
                break
        return []
    
    def is_available(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False


def create_llm_client(config: LLMConfig):
    """설정에 따라 적절한 LLM 클라이언트 생성"""
    if config.provider == LLMProvider.OLLAMA:
        return OllamaClient(config)
    elif config.provider == LLMProvider.OPENAI:
        return OpenAICompatibleClient(config)
    else:
        # 기본값: Ollama
        return OllamaClient(config)


# 하위 호환성을 위한 별칭
LLMClient = OllamaClient


class MockLLMClient:
    """테스트용 Mock LLM 클라이언트"""
    
    def __init__(self):
        self.config = LLMConfig(endpoint="mock://localhost")
    
    def detect_sensitive_keys(self, content: str) -> List[str]:
        """간단한 규칙 기반 탐지 (테스트용)"""
        sensitive_keywords = [
            'password', 'secret', 'key', 'token', 'credential',
            'private', 'auth', 'api_key', 'apikey'
        ]
        
        found_keys = []
        lines = content.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            for keyword in sensitive_keywords:
                if keyword in line_lower and '=' in line:
                    key = line.split('=')[0].strip()
                    if key and key not in found_keys:
                        found_keys.append(key)
                elif keyword in line_lower and ':' in line:
                    key = line.split(':')[0].strip()
                    if key and key not in found_keys:
                        found_keys.append(key)
        
        return found_keys
    
    def is_available(self) -> bool:
        return True
