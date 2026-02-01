"""
리포트 생성 모듈

마스킹 작업 결과에 대한 리포트를 생성합니다.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

import yaml


@dataclass
class FileReport:
    """개별 파일의 마스킹 리포트"""
    file_path: str
    relative_path: str
    masked_count: int
    masked_items: List[Dict[str, Any]] = field(default_factory=list)
    backup_path: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        return self.error is None


@dataclass
class MaskingReport:
    """전체 마스킹 작업 리포트"""
    project_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_files_scanned: int = 0
    total_files_masked: int = 0
    total_items_masked: int = 0
    files: List[FileReport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    config_used: Dict[str, Any] = field(default_factory=dict)
    llm_used: bool = False
    dry_run: bool = False
    
    def add_file_report(self, file_report: FileReport):
        """파일 리포트 추가"""
        self.files.append(file_report)
        self.total_files_scanned += 1
        
        if file_report.is_success and file_report.masked_count > 0:
            self.total_files_masked += 1
            self.total_items_masked += file_report.masked_count
        
        if file_report.error:
            self.errors.append(f"{file_report.file_path}: {file_report.error}")
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'project_path': self.project_path,
            'timestamp': self.timestamp,
            'summary': {
                'total_files_scanned': self.total_files_scanned,
                'total_files_masked': self.total_files_masked,
                'total_items_masked': self.total_items_masked,
                'has_errors': len(self.errors) > 0
            },
            'files': [asdict(f) for f in self.files],
            'errors': self.errors,
            'settings': {
                'llm_used': self.llm_used,
                'dry_run': self.dry_run
            }
        }


class ReportGenerator:
    """리포트 생성기"""
    
    def __init__(self, output_format: str = 'json'):
        """
        Args:
            output_format: 출력 형식 ('json', 'yaml', 'text')
        """
        self.output_format = output_format
    
    def generate(self, report: MaskingReport) -> str:
        """
        리포트를 문자열로 생성합니다.
        
        Args:
            report: MaskingReport 객체
            
        Returns:
            형식화된 리포트 문자열
        """
        if self.output_format == 'json':
            return self._generate_json(report)
        elif self.output_format == 'yaml':
            return self._generate_yaml(report)
        else:
            return self._generate_text(report)
    
    def _generate_json(self, report: MaskingReport) -> str:
        """JSON 형식 리포트 생성"""
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    
    def _generate_yaml(self, report: MaskingReport) -> str:
        """YAML 형식 리포트 생성"""
        return yaml.dump(report.to_dict(), allow_unicode=True, default_flow_style=False)
    
    def _generate_text(self, report: MaskingReport) -> str:
        """텍스트 형식 리포트 생성"""
        lines = [
            "=" * 60,
            "마스킹 리포트",
            "=" * 60,
            f"프로젝트: {report.project_path}",
            f"실행 시간: {report.timestamp}",
            f"LLM 사용: {'예' if report.llm_used else '아니오'}",
            f"Dry Run: {'예' if report.dry_run else '아니오'}",
            "",
            "-" * 60,
            "요약",
            "-" * 60,
            f"스캔된 파일 수: {report.total_files_scanned}",
            f"마스킹된 파일 수: {report.total_files_masked}",
            f"마스킹된 항목 수: {report.total_items_masked}",
            "",
        ]
        
        if report.files:
            lines.extend([
                "-" * 60,
                "마스킹된 파일 상세",
                "-" * 60,
            ])
            
            for file_report in report.files:
                if file_report.masked_count > 0:
                    lines.append(f"\n파일: {file_report.relative_path}")
                    lines.append(f"  마스킹 항목 수: {file_report.masked_count}")
                    
                    if file_report.backup_path:
                        lines.append(f"  백업: {file_report.backup_path}")
                    
                    for item in file_report.masked_items:
                        lines.append(f"  - Line {item['line']}: {item['key']}")
        
        if report.errors:
            lines.extend([
                "",
                "-" * 60,
                "오류",
                "-" * 60,
            ])
            for error in report.errors:
                lines.append(f"  - {error}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return '\n'.join(lines)
    
    def save(self, report: MaskingReport, output_path: str):
        """
        리포트를 파일로 저장합니다.
        
        Args:
            report: MaskingReport 객체
            output_path: 저장할 파일 경로
        """
        content = self.generate(report)
        
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)


class ConsoleReporter:
    """콘솔 출력용 리포터 (Rich 라이브러리 사용)"""
    
    def __init__(self):
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.progress import Progress, SpinnerColumn, TextColumn
            self.console = Console()
            self.rich_available = True
        except ImportError:
            self.rich_available = False
    
    def print_header(self, text: str):
        """헤더 출력"""
        if self.rich_available:
            from rich.panel import Panel
            self.console.print(Panel(text, style="bold blue"))
        else:
            print(f"\n{'=' * 60}")
            print(f"  {text}")
            print(f"{'=' * 60}\n")
    
    def print_file_processed(self, file_path: str, masked_count: int, is_dry_run: bool = False):
        """파일 처리 결과 출력"""
        status = "[DRY RUN] " if is_dry_run else ""
        if self.rich_available:
            if masked_count > 0:
                self.console.print(f"  [green]✓[/green] {status}{file_path} - [yellow]{masked_count}[/yellow] items masked")
            else:
                self.console.print(f"  [dim]○[/dim] {status}{file_path} - no sensitive data found")
        else:
            symbol = "✓" if masked_count > 0 else "○"
            print(f"  {symbol} {status}{file_path} - {masked_count} items masked")
    
    def print_error(self, message: str):
        """오류 메시지 출력"""
        if self.rich_available:
            self.console.print(f"  [red]✗[/red] Error: {message}")
        else:
            print(f"  ✗ Error: {message}")
    
    def print_summary(self, report: MaskingReport):
        """요약 출력"""
        if self.rich_available:
            from rich.table import Table
            
            table = Table(title="마스킹 요약")
            table.add_column("항목", style="cyan")
            table.add_column("값", style="green")
            
            table.add_row("스캔된 파일", str(report.total_files_scanned))
            table.add_row("마스킹된 파일", str(report.total_files_masked))
            table.add_row("마스킹된 항목", str(report.total_items_masked))
            table.add_row("오류", str(len(report.errors)))
            
            self.console.print()
            self.console.print(table)
        else:
            print(f"\n요약:")
            print(f"  스캔된 파일: {report.total_files_scanned}")
            print(f"  마스킹된 파일: {report.total_files_masked}")
            print(f"  마스킹된 항목: {report.total_items_masked}")
            print(f"  오류: {len(report.errors)}")
    
    def print_warning(self, message: str):
        """경고 메시지 출력"""
        if self.rich_available:
            self.console.print(f"  [yellow]⚠[/yellow] Warning: {message}")
        else:
            print(f"  ⚠ Warning: {message}")
    
    def print_info(self, message: str):
        """정보 메시지 출력"""
        if self.rich_available:
            self.console.print(f"  [blue]ℹ[/blue] {message}")
        else:
            print(f"  ℹ {message}")
