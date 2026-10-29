import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def updater():
    script = Path(__file__).resolve().parents[1] / "updateAppsFromGithub.py"
    spec = importlib.util.spec_from_file_location("updateAppsFromGithub", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

from datetime import datetime, timezone


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Write a human-readable report after each pytest run."""
    stats = terminalreporter.stats
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    errors = len(stats.get("error", []))
    skipped = len(stats.get("skipped", []))
    success = exitstatus == 0
    report = [
        "# 🧪 Python 自动化测试报告",
        "",
        f"- **执行时间 (UTC)**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **整体状态**: {'✅ 通过 (Passed)' if success else '❌ 失败 (Failed)'}",
        "- **测试框架**: pytest（本地 / GitHub Actions）",
        f"- **退出状态码**: {exitstatus}",
        f"- **测试统计**: 通过 {passed} / 失败 {failed} / 错误 {errors} / 跳过 {skipped}",
        "",
        "---",
        "",
        "### 测试用例",
        "",
    ]
    for outcome in ("passed", "failed", "error", "skipped"):
        for item in stats.get(outcome, []):
            nodeid = getattr(item, "nodeid", "unknown")
            report.append(f"- **{nodeid}**: {outcome}")
    if not any(stats.get(x) for x in ("passed", "failed", "error", "skipped")):
        report.append("- 未收集到测试结果")
    report.extend(["", "### 失败详情", ""])
    issues = list(stats.get("failed", [])) + list(stats.get("error", []))
    if issues:
        for item in issues:
            name = getattr(item, "nodeid", "unknown")
            details = str(getattr(item, "longreprtext", "")).strip()
            report.extend([f"#### {name}", "", "```text", details[:6000], "```", ""])
    else:
        report.append("无失败用例；如整体状态失败，请查看 Actions 日志。")
    report.extend(["", "### 🤖 给 Codex 的反馈指引", "", "如果测试失败，请结合 GitHub Actions 日志与本报告定位问题。", ""])
    output = Path(__file__).resolve().parents[1] / "test_report.md"
    output.write_text("\n".join(report), encoding="utf-8")
