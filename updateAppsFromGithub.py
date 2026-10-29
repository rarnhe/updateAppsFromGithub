import json
import os
import platform
import re
import ssl
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

# 获取 Windows 的 %APPDATA%\Github 路径
appdata_path = os.getenv("LOCALAPPDATA") or (Path.home() / "Applications")
BASE_DOWNLOAD_DIR = Path(appdata_path) / Path(sys.argv[0]).stem
# 确保目标输出目录已自动创建
BASE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# GitHub Personal Access Token (可选，频繁运行建议填入)
GITHUB_TOKEN = ""

# 配置列表
CONFIGS = [
    {"repo": "Neilooo/md-reader", "keywords": "zip;portable"},
    {"repo": "Vscodium/vscodium", "keywords": "zip"},
    {"repo": "ramensoftware/windhawk", "keywords": "offline"},
    {"repo": "patui/Nosub", "keywords": "7z"},
    {"repo": "mihomo-party-org/clash-party", "keywords": "clash;windows;portable;7z"},
]

# 全局忽略 SSL 证书校验上下文
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def get_system_arch_tokens() -> tuple[list[str], list[str], list[str], list[str]]:
    """获取宿主机的特征词表（包含正向同义词与反向排斥词）"""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()

    # 1. 操作系统特征与排斥词
    if "win" in sys_name:
        os_tokens = ["win", "windows"]
        conflict_os = ["linux", "mac", "macos", "darwin", "android"]
    elif "linux" in sys_name:
        os_tokens = ["linux"]
        conflict_os = ["win", "windows", "mac", "macos", "darwin"]
    elif "darwin" in sys_name:
        os_tokens = ["mac", "macos", "darwin"]
        conflict_os = ["win", "windows", "linux"]
    else:
        os_tokens = [sys_name]
        conflict_os = []

    # 2. CPU 架构特征与排斥词
    if machine in ["amd64", "x86_64", "x64"]:
        arch_tokens = ["x64", "amd64", "x86_64"]
        conflict_arch = ["arm64", "aarch64", "armv7", "arm", "x86", "sha1", "sha256"]
    elif machine in ["arm64", "aarch64"]:
        arch_tokens = ["arm64", "aarch64"]
        conflict_arch = ["x64", "amd64", "x86_64", "armv7", "arm", "x86", "sha1", "sha256"]
    elif machine in ["x86"]:
        arch_tokens = ["x86", "win32"]
        conflict_arch = ["x64", "amd64", "x86_64", "arm64", "aarch64", "sha1", "sha256"]
    else:
        arch_tokens = [machine]
        conflict_arch = []
    return os_tokens, conflict_os, arch_tokens, conflict_arch


def is_token_in_name(token: str, name: str) -> bool:
    """使用正则边界检查词汇，防止子串误杀"""
    pattern = rf"(?:^|[^a-zA-Z0-9_]){re.escape(token)}(?:$|[^a-zA-Z0-9_])"
    return bool(re.search(pattern, name, re.IGNORECASE))


def fetch_repo_info(repo: str) -> dict:
    """获取 GitHub 仓库的基本元数据（包含 About/Description）"""
    url = f"https://api.github.com/repos/{repo}"
    headers = {"User-Agent": "Python-Portable-App-Updater"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, context=SSL_CONTEXT) as response:
        if response.status == 200:
            return json.loads(response.read().decode("utf-8"))
        else:
            raise RuntimeError(f"请求 GitHub Repo API 失败，HTTP 状态码: {response.status}")


def fetch_latest_release(repo: str) -> dict:
    """调用 GitHub API 获取最新的 Release 元数据"""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"User-Agent": "Python-Portable-App-Updater"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, context=SSL_CONTEXT) as response:
        if response.status == 200:
            return json.loads(response.read().decode("utf-8"))
        else:
            raise RuntimeError(f"请求 GitHub Release API 失败，HTTP 状态码: {response.status}")


def download_file(url: str, dest_path: Path, max_workers: int = 8):
    """多线程分片并发下载"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Python-Portable-App-Updater"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    req = Request(url, headers=headers)
    with urlopen(req, context=SSL_CONTEXT) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        accept_ranges = response.headers.get("Accept-Ranges", "").lower() == "bytes"

    if total_size == 0 or not accept_ranges:
        print("目标不支持分片下载，退回单线程高速下载...")
        with urlopen(req, context=SSL_CONTEXT) as response, open(dest_path, "wb") as out_file:
            chunk_size = 4 * 1024 * 1024
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
        print("下载完成!")
        return

    with open(dest_path, "wb") as f:
        f.seek(total_size - 1)
        f.write(b"\0")

    part_size = total_size // max_workers
    ranges = []
    for i in range(max_workers):
        start = i * part_size
        end = (i + 1) * part_size - 1 if i < max_workers - 1 else total_size - 1
        ranges.append((start, end))

    downloaded_bytes = 0

    def download_range(start: int, end: int):
        nonlocal downloaded_bytes
        thread_headers = headers.copy()
        thread_headers["Range"] = f"bytes={start}-{end}"
        thread_req = Request(url, headers=thread_headers)
        with urlopen(thread_req, context=SSL_CONTEXT) as resp, open(dest_path, "r+b") as f:
            f.seek(start)
            chunk_size = 1024 * 1024
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded_bytes += len(chunk)
                percent = (downloaded_bytes / total_size) * 100
                print(
                    f"\r多线程下载中 ({max_workers} 线程): {percent:.1f}% ({downloaded_bytes // (1024*1024)}MB / {total_size // (1024*1024)}MB)",
                    end="",
                )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_range, s, e) for s, e in ranges]
        for future in futures:
            future.result()
    print("\n下载完成!")


def filter_assets(
    assets: list,
    keywords_str: str,
    os_tokens: list[str],
    conflict_os: list[str],
    arch_tokens: list[str],
    conflict_arch: list[str],
) -> tuple[dict | None, list]:
    """无版本号的三步漏斗筛选"""
    if not assets:
        return None, []
    user_keywords = [k.strip().lower() for k in keywords_str.split(";") if k.strip()]

    stage1_candidates = []
    for asset in assets:
        name = asset.get("name", "").lower()
        if all(kw in name for kw in user_keywords):
            stage1_candidates.append(asset)
    if not stage1_candidates:
        print(f"[错误提示] 步骤1筛选失败：未找到包含关键词 ({keywords_str}) 的 Asset。")
        return None, []

    stage2_candidates = []
    for asset in stage1_candidates:
        name = asset.get("name", "").lower()
        has_os_conflict = any(is_token_in_name(c_os, name) for c_os in conflict_os)
        has_arch_conflict = any(is_token_in_name(c_arch, name) for c_arch in conflict_arch)
        if not has_os_conflict and not has_arch_conflict:
            stage2_candidates.append(asset)
    if len(stage2_candidates) == 0:
        print(f"[错误提示] 步骤2排除失败：排除冲突平台后无剩余 Asset，请检查 keywords ({keywords_str})。")
        return None, stage1_candidates
    if len(stage2_candidates) == 1:
        return stage2_candidates[0], stage2_candidates

    stage3_candidates = []
    for asset in stage2_candidates:
        name = asset.get("name", "").lower()
        if any(is_token_in_name(arch_kw, name) for arch_kw in arch_tokens):
            stage3_candidates.append(asset)
    if len(stage3_candidates) == 1:
        return stage3_candidates[0], stage3_candidates
    final_candidates = stage3_candidates if stage3_candidates else stage2_candidates
    return None, final_candidates


def process_app(
    config: dict,
    os_tokens: list[str],
    conflict_os: list[str],
    arch_tokens: list[str],
    conflict_arch: list[str],
):
    """处理单个仓库的检查、下载与解压"""
    repo = config["repo"]
    keywords = config.get("keywords", "")
    print(f"\n======== 检查仓库: {repo} ========")
    try:
        # 获取并展示仓库 About 信息
        repo_info = fetch_repo_info(repo)
        description = repo_info.get("description") or "暂无 About 描述"
        print(f"[简介] {description}")
        release_data = fetch_latest_release(repo)
        assets = release_data.get("assets", [])
        target_asset, last_candidates = filter_assets(
            assets, keywords, os_tokens, conflict_os, arch_tokens, conflict_arch,
        )
        if not target_asset:
            print("[无法锁定] 经过筛选后仍存在多个（或零个）候选，请参考最后保留的 Asset 列表补充 keywords 区分:")
            candidates_to_show = last_candidates if last_candidates else assets
            for a in candidates_to_show:
                print(f"  - {a.get('name')}")
            return

        target_file_name = target_asset.get("name")
        download_url = target_asset.get("browser_download_url")
        file_path = BASE_DOWNLOAD_DIR / target_file_name
        is_zip_file = target_file_name.lower().endswith(".zip")
        if is_zip_file:
            extract_dir = BASE_DOWNLOAD_DIR / file_path.stem
            if extract_dir.exists():
                print(f"[跳过] 本地已存在匹配文件夹: {file_path.stem}")
                return
        else:
            if file_path.exists():
                print(f"[跳过] 本地已存在最新文件: {target_file_name}")
                return

        print(f"精准锁定 Asset: {target_file_name}")
        print("准备下载...")
        download_file(download_url, file_path)
        if is_zip_file:
            extract_dir = BASE_DOWNLOAD_DIR / file_path.stem
            print(f"正在解压至: {extract_dir}")
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            print("正在清理临时压缩包...")
            file_path.unlink()
        else:
            print(f"非 ZIP 压缩文件，已直接保存至: {file_path}")
        print(f"✔ {repo} 处理完毕！")
    except Exception as e:
        print(f"[运行异常] 处理 {repo} 时发生错误: {e}")


def main():
    os_tokens, conflict_os, arch_tokens, conflict_arch = get_system_arch_tokens()
    print("开始检查开源绿色软件更新...")
    print(f"解压与保存根路径: {BASE_DOWNLOAD_DIR}")
    print(f"宿主系统匹配词: {os_tokens} (排斥: {conflict_os})")
    print(f"宿主架构匹配词: {arch_tokens} (排斥: {conflict_arch})")
    for config in CONFIGS:
        process_app(config, os_tokens, conflict_os, arch_tokens, conflict_arch)
    print("\n所有任务执行完毕！")


if __name__ == "__main__":
    main()
