"""
핵심 마스킹 엔진 모듈

YAML, Properties, ENV 파일의 민감 정보를 마스킹 처리합니다.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import yaml


@dataclass
class MaskingResult:
    """마스킹 결과를 담는 데이터 클래스"""
    file_path: str
    original_content: str
    masked_content: str
    masked_items: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        return self.error is None
    
    @property
    def masked_count(self) -> int:
        return len(self.masked_items)


class SensitivePatternMatcher:
    """민감 정보 패턴 매칭 클래스"""
    
    def __init__(
        self,
        key_patterns: List[str],
        value_patterns: List[str] = None,
        exclude_key_patterns: List[str] = None,
        exclude_value_patterns: List[str] = None
    ):
        self.key_patterns = [re.compile(p, re.IGNORECASE) for p in key_patterns]
        self.value_patterns = [re.compile(p) for p in (value_patterns or [])]
        self.exclude_key_patterns = [re.compile(p, re.IGNORECASE) for p in (exclude_key_patterns or [])]
        self.exclude_value_patterns = [re.compile(p) for p in (exclude_value_patterns or [])]
    
    def is_sensitive_key(self, key: str) -> bool:
        """키가 민감한 정보를 나타내는지 확인"""
        # 제외 패턴 먼저 확인
        for pattern in self.exclude_key_patterns:
            if pattern.search(key):
                return False
        
        # 민감 정보 패턴 확인
        for pattern in self.key_patterns:
            if pattern.search(key):
                return True
        
        return False
    
    def is_sensitive_value(self, value: str) -> bool:
        """값 자체가 민감한 정보인지 확인"""
        if not isinstance(value, str):
            return False
            
        # 제외 패턴 먼저 확인
        for pattern in self.exclude_value_patterns:
            if pattern.match(value):
                return False
        
        # 민감 정보 값 패턴 확인
        for pattern in self.value_patterns:
            if pattern.match(value):
                return True
        
        return False
    
    def should_mask(self, key: str, value: Any) -> bool:
        """해당 키-값 쌍이 마스킹 대상인지 확인"""
        if value is None or value == "":
            return False
            
        # 이미 마스킹된 값인지 확인
        if isinstance(value, str) and value.startswith("***") and value.endswith("***"):
            return False
            
        return self.is_sensitive_key(key) or (isinstance(value, str) and self.is_sensitive_value(value))


class YamlMasker:
    """YAML 파일 마스킹 처리기"""
    
    def __init__(self, matcher: SensitivePatternMatcher, mask_format: str = "***MASKED***"):
        self.matcher = matcher
        self.mask_format = mask_format
    
    def mask_content(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        YAML 콘텐츠를 마스킹 처리
        
        Returns:
            Tuple[마스킹된 콘텐츠, 마스킹된 항목 리스트]
        """
        masked_items = []
        lines = content.split('\n')
        result_lines = []
        
        # YAML 파싱을 위한 현재 키 경로 추적
        key_stack = []
        indent_stack = [0]
        
        for line_num, line in enumerate(lines, 1):
            # 빈 줄이나 주석은 그대로 유지
            if not line.strip() or line.strip().startswith('#'):
                result_lines.append(line)
                continue
            
            # 현재 줄의 들여쓰기 레벨 계산
            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)
            
            # 들여쓰기에 따라 키 스택 조정
            while len(indent_stack) > 1 and current_indent <= indent_stack[-1]:
                indent_stack.pop()
                if key_stack:
                    key_stack.pop()
            
            # 키-값 쌍 파싱
            if ':' in stripped and not stripped.startswith('-'):
                key_part = stripped.split(':', 1)[0].strip()
                value_part = stripped.split(':', 1)[1].strip() if ':' in stripped else ""
                
                # 전체 키 경로 생성
                full_key = '.'.join(key_stack + [key_part]) if key_stack else key_part
                
                # 값이 있는 경우 마스킹 여부 확인
                if value_part and not value_part.startswith('#'):
                    # 인용부호 제거하여 실제 값 확인
                    actual_value = value_part.strip('"\'')
                    
                    if self.matcher.should_mask(full_key, actual_value):
                        # 마스킹 처리
                        original_value = value_part
                        masked_line = line.replace(value_part, f'"{self.mask_format}"', 1)
                        result_lines.append(masked_line)
                        
                        masked_items.append({
                            'line': line_num,
                            'key': full_key,
                            'original_value': actual_value,
                            'type': 'yaml'
                        })
                        continue
                else:
                    # 하위 키가 있을 수 있으므로 스택에 추가
                    key_stack.append(key_part)
                    indent_stack.append(current_indent)
            
            result_lines.append(line)
        
        return '\n'.join(result_lines), masked_items


class PropertiesMasker:
    """Properties 파일 마스킹 처리기"""
    
    def __init__(self, matcher: SensitivePatternMatcher, mask_format: str = "***MASKED***"):
        self.matcher = matcher
        self.mask_format = mask_format
    
    def mask_content(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Properties 콘텐츠를 마스킹 처리
        
        Returns:
            Tuple[마스킹된 콘텐츠, 마스킹된 항목 리스트]
        """
        masked_items = []
        lines = content.split('\n')
        result_lines = []
        
        for line_num, line in enumerate(lines, 1):
            # 빈 줄이나 주석은 그대로 유지
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith('!'):
                result_lines.append(line)
                continue
            
            # 키=값 또는 키:값 파싱
            match = re.match(r'^([^=:]+)[=:](.*)$', line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                
                if self.matcher.should_mask(key, value):
                    # 마스킹 처리 (원래 구분자 유지)
                    separator = '=' if '=' in line else ':'
                    masked_line = f"{key}{separator}{self.mask_format}"
                    result_lines.append(masked_line)
                    
                    masked_items.append({
                        'line': line_num,
                        'key': key,
                        'original_value': value,
                        'type': 'properties'
                    })
                    continue
            
            result_lines.append(line)
        
        return '\n'.join(result_lines), masked_items


class EnvMasker:
    """ENV 파일 마스킹 처리기"""
    
    def __init__(self, matcher: SensitivePatternMatcher, mask_format: str = "***MASKED***"):
        self.matcher = matcher
        self.mask_format = mask_format
    
    def mask_content(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        ENV 콘텐츠를 마스킹 처리
        
        Returns:
            Tuple[마스킹된 콘텐츠, 마스킹된 항목 리스트]
        """
        masked_items = []
        lines = content.split('\n')
        result_lines = []
        
        for line_num, line in enumerate(lines, 1):
            # 빈 줄이나 주석은 그대로 유지
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                result_lines.append(line)
                continue
            
            # KEY=VALUE 파싱
            match = re.match(r'^(export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
            if match:
                export_prefix = match.group(1) or ''
                key = match.group(2)
                value = match.group(3).strip('"\'')
                
                if self.matcher.should_mask(key, value):
                    # 마스킹 처리
                    masked_line = f'{export_prefix}{key}="{self.mask_format}"'
                    result_lines.append(masked_line)
                    
                    masked_items.append({
                        'line': line_num,
                        'key': key,
                        'original_value': value,
                        'type': 'env'
                    })
                    continue
            
            result_lines.append(line)
        
        return '\n'.join(result_lines), masked_items


class MaskingEngine:
    """
    통합 마스킹 엔진
    
    파일 유형에 따라 적절한 마스커를 선택하여 처리합니다.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 설정 딕셔너리
        """
        self.config = config
        self.mask_format = config.get('mask_format', '***MASKED***')
        
        # 패턴 매처 초기화
        self.matcher = SensitivePatternMatcher(
            key_patterns=config.get('sensitive_key_patterns', []),
            value_patterns=config.get('sensitive_value_patterns', []),
            exclude_key_patterns=config.get('exclude_key_patterns', []),
            exclude_value_patterns=config.get('exclude_value_patterns', [])
        )
        
        # 파일 유형별 마스커 초기화
        self.yaml_masker = YamlMasker(self.matcher, self.mask_format)
        self.properties_masker = PropertiesMasker(self.matcher, self.mask_format)
        self.env_masker = EnvMasker(self.matcher, self.mask_format)
    
    def mask_file(self, file_path: str, content: str) -> MaskingResult:
        """
        파일 내용을 마스킹 처리
        
        Args:
            file_path: 파일 경로
            content: 파일 내용
            
        Returns:
            MaskingResult 객체
        """
        try:
            # 파일 유형에 따라 적절한 마스커 선택
            if file_path.endswith(('.yml', '.yaml')):
                masked_content, masked_items = self.yaml_masker.mask_content(content)
            elif file_path.endswith('.properties'):
                masked_content, masked_items = self.properties_masker.mask_content(content)
            elif file_path.endswith('.env') or '.env' in file_path:
                masked_content, masked_items = self.env_masker.mask_content(content)
            else:
                # 기본적으로 properties 형식으로 처리
                masked_content, masked_items = self.properties_masker.mask_content(content)
            
            return MaskingResult(
                file_path=file_path,
                original_content=content,
                masked_content=masked_content,
                masked_items=masked_items
            )
            
        except Exception as e:
            return MaskingResult(
                file_path=file_path,
                original_content=content,
                masked_content=content,
                error=str(e)
            )
    
    def add_sensitive_patterns(self, patterns: List[str]):
        """LLM이 탐지한 추가 민감 패턴을 추가"""
        for pattern in patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.matcher.key_patterns.append(compiled)
            except re.error:
                # 유효하지 않은 정규식은 무시
                pass
