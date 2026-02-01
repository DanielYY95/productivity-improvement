#!/usr/bin/env python3
"""
Spring/Spring Boot 프로젝트 민감 정보 마스킹 도구

CLI 진입점
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

import click
import yaml

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.masker import MaskingEngine, MaskingResult
from src.scanner import FileScanner, BackupManager, FileProcessor
from src.llm_client import LLMConfig, OllamaClient, create_llm_client, MockLLMClient
from src.reporter import (
    MaskingReport, FileReport, ReportGenerator, ConsoleReporter
)


def load_config(config_path: str = None) -> dict:
    """설정 파일 로드"""
    # 기본 설정 파일 경로
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    # 기본 설정 반환
    return {
        'file_patterns': [
            'application.properties',
            'application.yml',
            'application.yaml',
            'application-*.yml',
            'application-*.yaml',
            'application-*.properties',
            '*.env',
            '.env',
            'bootstrap.yml',
            'bootstrap.properties',
        ],
        'exclude_dirs': [
            '.git', 'node_modules', 'target', 'build', '.idea', '.vscode'
        ],
        'sensitive_key_patterns': [
            'password', 'passwd', 'pwd', 'secret', 'token',
            'api[-_]?key', 'private[-_]?key', 'credential',
            'auth[-_]?token', 'encrypt', 'signing[-_]?key'
        ],
        'mask_format': '***MASKED***'
    }


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """Spring/Spring Boot 프로젝트 민감 정보 마스킹 도구
    
    설정 파일(application.yml, application.properties, .env 등)에서
    비밀번호, API 키, 토큰 등 민감한 정보를 자동으로 탐지하고 마스킹합니다.
    """
    pass


@cli.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(exists=True), help='커스텀 설정 파일 경로')
@click.option('--no-backup', is_flag=True, help='백업 없이 원본 파일 직접 수정')
@click.option('--dry-run', '-n', is_flag=True, help='미리보기 모드 (실제 파일 변경 없음)')
@click.option('--use-llm', is_flag=True, help='LLM 기반 고급 탐지 활성화')
@click.option('--include', '-i', multiple=True, help='포함할 파일 패턴')
@click.option('--exclude', '-e', multiple=True, help='제외할 파일/폴더 패턴')
@click.option('--output', '-o', type=click.Path(), help='리포트 출력 파일')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), default='json', help='리포트 형식')
@click.option('--verbose', '-v', is_flag=True, help='상세 출력')
def mask(
    paths: tuple,
    config: Optional[str],
    no_backup: bool,
    dry_run: bool,
    use_llm: bool,
    include: tuple,
    exclude: tuple,
    output: Optional[str],
    output_format: str,
    verbose: bool
):
    """프로젝트의 민감 정보를 마스킹합니다.
    
    예시:
    
        # 현재 디렉토리 마스킹
        python main.py mask .
        
        # 특정 프로젝트 마스킹
        python main.py mask /path/to/project
        
        # 미리보기 모드
        python main.py mask . --dry-run
        
        # LLM 활성화
        python main.py mask . --use-llm
    """
    # 경로가 지정되지 않으면 현재 디렉토리 사용
    if not paths:
        paths = ('.',)
    
    # 설정 로드
    cfg = load_config(config)
    
    # 콘솔 리포터 초기화
    console = ConsoleReporter()
    
    # 헤더 출력
    mode_str = "[DRY RUN] " if dry_run else ""
    console.print_header(f"{mode_str}Spring/Spring Boot 민감 정보 마스킹")
    
    if dry_run:
        console.print_warning("Dry run 모드: 실제 파일은 변경되지 않습니다.")
    
    # 스캐너 초기화
    scanner = FileScanner(
        file_patterns=cfg.get('file_patterns', []),
        exclude_dirs=cfg.get('exclude_dirs', []),
        include_patterns=list(include) if include else None,
        exclude_patterns=list(exclude) if exclude else None
    )
    
    # 백업 매니저 초기화
    backup_config = cfg.get('backup', {})
    backup_manager = None if no_backup else BackupManager(
        backup_dir_name=backup_config.get('directory', '.masking_backup'),
        suffix=backup_config.get('suffix', '.backup')
    )
    
    # 파일 프로세서 초기화
    file_processor = FileProcessor(backup_manager)
    
    # 마스킹 엔진 초기화
    engine = MaskingEngine(cfg)
    
    # LLM 클라이언트 초기화 (Ollama)
    llm_client = None
    if use_llm:
        llm_config = LLMConfig.from_dict(cfg)
        llm_client = create_llm_client(llm_config)
        
        # Ollama 연결 확인
        if llm_client.is_available():
            console.print_info(f"Ollama LLM 연결됨: {llm_config.endpoint} (모델: {llm_config.model})")
        else:
            console.print_warning(f"Ollama 연결 실패 또는 모델 '{llm_config.model}' 없음. 'ollama pull {llm_config.model}' 실행 필요.")
            console.print_warning("LLM 없이 패턴 기반 탐지만 사용합니다.")
            llm_client = None
    
    # 각 프로젝트 경로 처리
    for project_path in paths:
        project_path = os.path.abspath(project_path)
        
        console.print_info(f"프로젝트 스캔 중: {project_path}")
        
        # 리포트 초기화
        report = MaskingReport(
            project_path=project_path,
            llm_used=use_llm and llm_client is not None,
            dry_run=dry_run
        )
        
        # 파일 스캔 및 처리
        for file_path in scanner.scan(project_path):
            rel_path = os.path.relpath(file_path, project_path)
            
            try:
                # 파일 읽기
                content = file_processor.read_file(file_path)
                
                # LLM을 통한 추가 패턴 탐지
                if llm_client:
                    try:
                        llm_keys = llm_client.detect_sensitive_keys(content)
                        if llm_keys:
                            engine.add_sensitive_patterns(llm_keys)
                            if verbose:
                                console.print_info(f"LLM이 탐지한 추가 키: {llm_keys}")
                    except Exception as e:
                        console.print_warning(f"LLM 탐지 실패: {e}")
                
                # 마스킹 처리
                result = engine.mask_file(file_path, content)
                
                # 파일 저장 (dry_run이 아닐 때만)
                if not dry_run and result.masked_count > 0:
                    backup_path = None
                    if backup_manager:
                        backup_path = backup_manager.create_backup(file_path, project_path)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(result.masked_content)
                    
                    file_report = FileReport(
                        file_path=file_path,
                        relative_path=rel_path,
                        masked_count=result.masked_count,
                        masked_items=result.masked_items,
                        backup_path=backup_path
                    )
                else:
                    file_report = FileReport(
                        file_path=file_path,
                        relative_path=rel_path,
                        masked_count=result.masked_count,
                        masked_items=result.masked_items
                    )
                
                report.add_file_report(file_report)
                console.print_file_processed(rel_path, result.masked_count, dry_run)
                
                if verbose and result.masked_items:
                    for item in result.masked_items:
                        console.print_info(f"    Line {item['line']}: {item['key']}")
                
            except Exception as e:
                file_report = FileReport(
                    file_path=file_path,
                    relative_path=rel_path,
                    masked_count=0,
                    error=str(e)
                )
                report.add_file_report(file_report)
                console.print_error(f"{rel_path}: {e}")
        
        # 요약 출력
        console.print_summary(report)
        
        # 리포트 저장
        if output:
            generator = ReportGenerator(output_format)
            generator.save(report, output)
            console.print_info(f"리포트 저장됨: {output}")
        else:
            # 기본 리포트 파일
            default_output = os.path.join(project_path, f"masking_report.{output_format}")
            generator = ReportGenerator(output_format)
            generator.save(report, default_output)
            console.print_info(f"리포트 저장됨: {default_output}")


@cli.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
def restore(paths: tuple):
    """백업에서 원본 파일을 복원합니다.
    
    예시:
    
        python main.py restore /path/to/project
    """
    if not paths:
        paths = ('.',)
    
    console = ConsoleReporter()
    console.print_header("백업 복원")
    
    backup_manager = BackupManager()
    
    for project_path in paths:
        project_path = os.path.abspath(project_path)
        console.print_info(f"복원 중: {project_path}")
        
        restored = backup_manager.restore_all(project_path)
        
        if restored:
            for file_path in restored:
                rel_path = os.path.relpath(file_path, project_path)
                console.print_file_processed(rel_path, 0, False)
                console.print_info(f"복원됨: {rel_path}")
            console.print_info(f"총 {len(restored)}개 파일이 복원되었습니다.")
        else:
            console.print_warning("복원할 백업 파일이 없습니다.")


@cli.command()
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), default='text', help='출력 형식')
def report(path: str, output_format: str):
    """마스킹 리포트를 확인합니다.
    
    예시:
    
        python main.py report /path/to/project
    """
    project_path = os.path.abspath(path)
    
    # 리포트 파일 찾기
    for ext in ['json', 'yaml', 'txt']:
        report_path = os.path.join(project_path, f'masking_report.{ext}')
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if output_format == 'text' and ext == 'json':
                # JSON을 텍스트로 변환
                import json
                data = json.loads(content)
                print(f"\n프로젝트: {data.get('project_path', 'N/A')}")
                print(f"실행 시간: {data.get('timestamp', 'N/A')}")
                summary = data.get('summary', {})
                print(f"\n요약:")
                print(f"  스캔된 파일: {summary.get('total_files_scanned', 0)}")
                print(f"  마스킹된 파일: {summary.get('total_files_masked', 0)}")
                print(f"  마스킹된 항목: {summary.get('total_items_masked', 0)}")
            else:
                print(content)
            return
    
    print(f"리포트 파일을 찾을 수 없습니다: {project_path}")


@cli.command()
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--config', '-c', type=click.Path(exists=True), help='커스텀 설정 파일 경로')
def scan(path: str, config: Optional[str]):
    """프로젝트에서 마스킹 대상 파일을 스캔합니다 (파일 변경 없음).
    
    예시:
    
        python main.py scan /path/to/project
    """
    project_path = os.path.abspath(path)
    cfg = load_config(config)
    
    console = ConsoleReporter()
    console.print_header("설정 파일 스캔")
    
    scanner = FileScanner(
        file_patterns=cfg.get('file_patterns', []),
        exclude_dirs=cfg.get('exclude_dirs', [])
    )
    
    console.print_info(f"스캔 중: {project_path}")
    
    files = list(scanner.scan(project_path))
    
    if files:
        print(f"\n발견된 설정 파일 ({len(files)}개):\n")
        for file_path in files:
            rel_path = os.path.relpath(file_path, project_path)
            print(f"  • {rel_path}")
    else:
        console.print_warning("마스킹 대상 파일을 찾을 수 없습니다.")


@cli.command()
def init():
    """현재 디렉토리에 기본 설정 파일을 생성합니다.
    
    예시:
    
        python main.py init
    """
    config_path = os.path.join(os.getcwd(), 'masking_config.yml')
    
    if os.path.exists(config_path):
        click.confirm(f'{config_path} 파일이 이미 존재합니다. 덮어쓰시겠습니까?', abort=True)
    
    # 기본 설정 파일 복사
    default_config = os.path.join(os.path.dirname(__file__), 'config.yml')
    
    if os.path.exists(default_config):
        import shutil
        shutil.copy(default_config, config_path)
    else:
        # 기본 설정 생성
        default_config_content = """# 마스킹 설정 파일

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

# 제외할 디렉토리
exclude_dirs:
  - ".git"
  - "node_modules"
  - "target"
  - "build"

# 민감 정보 키 패턴
sensitive_key_patterns:
  - "password"
  - "secret"
  - "token"
  - "api[-_]?key"
  - "credential"

# 마스킹 형식
mask_format: "***MASKED***"

# 백업 설정
backup:
  enabled: true
  directory: ".masking_backup"
  suffix: ".backup"

# Ollama LLM 설정
llm:
  enabled: false
  provider: "ollama"
  endpoint: "http://localhost:11434"
  model: "gemma3:27b"
  timeout: 120
"""
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(default_config_content)
    
    click.echo(f'설정 파일이 생성되었습니다: {config_path}')


@cli.command()
@click.option('--endpoint', '-e', default='http://localhost:11434', help='Ollama 서버 주소')
def models(endpoint: str):
    """Ollama에서 사용 가능한 모델 목록을 확인합니다.
    
    예시:
    
        python main.py models
        python main.py models --endpoint http://192.168.1.100:11434
    """
    from src.llm_client import OllamaClient, LLMConfig
    
    console = ConsoleReporter()
    console.print_header("Ollama 모델 목록")
    
    config = LLMConfig(endpoint=endpoint)
    client = OllamaClient(config)
    
    try:
        models_list = client.list_models()
        
        if models_list:
            console.print_info(f"Ollama 서버: {endpoint}")
            print(f"\n사용 가능한 모델 ({len(models_list)}개):\n")
            for model in models_list:
                print(f"  • {model}")
            print()
        else:
            console.print_warning(f"Ollama 서버({endpoint})에서 모델을 찾을 수 없습니다.")
            console.print_info("'ollama pull gemma3:27b' 명령으로 모델을 설치하세요.")
    except Exception as e:
        console.print_error(f"Ollama 서버 연결 실패: {e}")
        console.print_info("Ollama가 실행 중인지 확인하세요: 'ollama serve'")



if __name__ == '__main__':
    cli()
