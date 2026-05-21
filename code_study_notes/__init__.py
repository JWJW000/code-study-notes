"""Code Study Notes: static codebase learning-note generator."""

from .analyzer import analyze_repository
from .report import render_markdown_report

__all__ = ["analyze_repository", "render_markdown_report"]

