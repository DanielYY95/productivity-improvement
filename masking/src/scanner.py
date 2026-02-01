"""
파일 탐색 모듈

프로젝트 디렉토리에서 마스킹 대상 파일을 탐색합니다.
"""

import os
import fnmatch
import shutil
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set
from datetime import datetime
import json


class FileScanner:
    """프로젝트 디렉토리에서 설정 파일을 탐색하는 클래스"""
    
    def __init__(
        self,
        file_patterns: List[str],
        exclude_dirs: List[str] = None,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ):
        """
        Args:
            file_patterns: 탐색할 파일 패턴 리스트
            exclude_dirs: 제외할 디렉토리 리스트
            include_patterns: 포함할 추가 패턴 (--include 옵션)
            exclude_patterns: 제외할 추가 패턴 (--exclude 옵션)
        """
        self.file_patterns = file_patterns
        self.exclude_dirs = set(exclude_dirs or [])
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
    
    def _should_exclude_dir(self, dir_name: str) -> bool:
        """디렉토리를 제외해야 하는지 확인"""
        return dir_name in self.exclude_dirs or dir_name.startswith('.')
    
    def _matches_pattern(self, filename: str, patterns: List[str]) -> bool:
        """파일명이 패턴 중 하나와 일치하는지 확인"""
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _should_process_file(self, file_path: str, filename: str) -> bool:
        """파일을 처리해야 하는지 확인"""
        # 추가 제외 패턴 확인
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(filename, pattern):
                    return False
        
        # 추가 포함 패턴이 지정된 경우 해당 패턴만 처리
        if self.include_patterns:
            return self._matches_pattern(filename, self.include_patterns)
        
        # 기본 파일 패턴 확인
        return self._matches_pattern(filename, self.file_patterns)
    
    def scan(self, project_path: str) -> Generator[str, None, None]:
        """
        프로젝트 디렉토리를 스캔하여 대상 파일을 찾습니다.
        
        Args:
            project_path: 프로젝트 루트 경로
            
        Yields:
            대상 파일의 절대 경로
        """
        project_path = os.path.abspath(project_path)
        
        for root, dirs, files in os.walk(project_path):
            # 제외할 디렉토리 필터링 (in-place 수정으로 하위 탐색 방지)
            dirs[:] = [d for d in dirs if not self._should_exclude_dir(d)]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, project_path)
                
                if self._should_process_file(rel_path, filename):
                    yield file_path
    
    def scan_multiple(self, project_paths: List[str]) -> Generator[str, None, None]:
        """
        여러 프로젝트 디렉토리를 스캔합니다.
        
        Args:
            project_paths: 프로젝트 경로 리스트
            
        Yields:
            대상 파일의 절대 경로
        """
        for project_path in project_paths:
            yield from self.scan(project_path)


class BackupManager:
    """백업 관리 클래스"""
    
    def __init__(self, backup_dir_name: str = ".masking_backup", suffix: str = ".backup"):
        """
        Args:
            backup_dir_name: 백업 디렉토리 이름
            suffix: 백업 파일 접미사
        """
        self.backup_dir_name = backup_dir_name
        self.suffix = suffix
        self._backup_manifest: Dict[str, str] = {}
    
    def _get_backup_dir(self, project_path: str) -> str:
        """프로젝트의 백업 디렉토리 경로 반환"""
        return os.path.join(project_path, self.backup_dir_name)
    
    def _get_backup_path(self, original_path: str, project_path: str) -> str:
        """원본 파일의 백업 경로 생성"""
        backup_dir = self._get_backup_dir(project_path)
        rel_path = os.path.relpath(original_path, project_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{rel_path.replace(os.sep, '_')}_{timestamp}{self.suffix}"
        return os.path.join(backup_dir, backup_filename)
    
    def create_backup(self, file_path: str, project_path: str) -> str:
        """
        파일의 백업을 생성합니다.
        
        Args:
            file_path: 백업할 파일 경로
            project_path: 프로젝트 루트 경로
            
        Returns:
            백업 파일 경로
        """
        backup_dir = self._get_backup_dir(project_path)
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = self._get_backup_path(file_path, project_path)
        shutil.copy2(file_path, backup_path)
        
        # 매니페스트에 기록
        self._backup_manifest[file_path] = backup_path
        self._save_manifest(project_path)
        
        return backup_path
    
    def _save_manifest(self, project_path: str):
        """백업 매니페스트 저장"""
        backup_dir = self._get_backup_dir(project_path)
        manifest_path = os.path.join(backup_dir, "manifest.json")
        
        # 기존 매니페스트 로드
        existing = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        
        # 업데이트
        existing.update(self._backup_manifest)
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    
    def restore_all(self, project_path: str) -> List[str]:
        """
        프로젝트의 모든 백업 파일을 복원합니다.
        
        Args:
            project_path: 프로젝트 루트 경로
            
        Returns:
            복원된 파일 경로 리스트
        """
        backup_dir = self._get_backup_dir(project_path)
        manifest_path = os.path.join(backup_dir, "manifest.json")
        
        if not os.path.exists(manifest_path):
            return []
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        restored = []
        for original_path, backup_path in manifest.items():
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, original_path)
                restored.append(original_path)
        
        return restored
    
    def get_latest_backup(self, file_path: str, project_path: str) -> Optional[str]:
        """
        파일의 가장 최근 백업 경로를 반환합니다.
        
        Args:
            file_path: 원본 파일 경로
            project_path: 프로젝트 루트 경로
            
        Returns:
            백업 파일 경로 또는 None
        """
        backup_dir = self._get_backup_dir(project_path)
        manifest_path = os.path.join(backup_dir, "manifest.json")
        
        if not os.path.exists(manifest_path):
            return None
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        return manifest.get(file_path)


class FileProcessor:
    """파일 처리를 담당하는 클래스"""
    
    def __init__(self, backup_manager: Optional[BackupManager] = None):
        """
        Args:
            backup_manager: 백업 매니저 인스턴스
        """
        self.backup_manager = backup_manager
    
    def read_file(self, file_path: str) -> str:
        """파일 내용 읽기"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def write_file(self, file_path: str, content: str, project_path: str = None, create_backup: bool = True):
        """
        파일 내용 쓰기
        
        Args:
            file_path: 파일 경로
            content: 쓸 내용
            project_path: 프로젝트 루트 경로 (백업용)
            create_backup: 백업 생성 여부
        """
        # 백업 생성
        if create_backup and self.backup_manager and project_path:
            self.backup_manager.create_backup(file_path, project_path)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def process_file(
        self,
        file_path: str,
        processor_func,
        project_path: str = None,
        create_backup: bool = True,
        dry_run: bool = False
    ):
        """
        파일을 읽고, 처리하고, 저장하는 일련의 과정을 수행합니다.
        
        Args:
            file_path: 처리할 파일 경로
            processor_func: 내용을 처리하는 함수 (content -> processed_content)
            project_path: 프로젝트 루트 경로
            create_backup: 백업 생성 여부
            dry_run: True면 실제 파일 변경 없음
            
        Returns:
            처리된 내용
        """
        content = self.read_file(file_path)
        processed_content = processor_func(content)
        
        if not dry_run and content != processed_content:
            self.write_file(file_path, processed_content, project_path, create_backup)
        
        return processed_content
