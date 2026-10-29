import io
import zipfile


def test_token_boundary(updater):
    assert updater.is_token_in_name("x64", "app-win-x64.zip")
    assert not updater.is_token_in_name("x86", "app-x86_64.zip")
    assert not updater.is_token_in_name("arm", "app-arm64.zip")


def test_host_tokens(updater, monkeypatch):
    monkeypatch.setattr(updater.platform, "system", lambda: "Windows")
    monkeypatch.setattr(updater.platform, "machine", lambda: "AMD64")
    os_tokens, os_exclusions, arch_tokens, arch_exclusions = updater.get_system_arch_tokens()
    assert "windows" in os_tokens
    assert "linux" in os_exclusions
    assert "x64" in arch_tokens
    assert "arm64" in arch_exclusions


def test_filter_assets(updater):
    assets = [
        {"name": "tool-linux-x64-portable.zip"},
        {"name": "tool-windows-arm64-portable.zip"},
        {"name": "tool-windows-x64-portable.zip"},
    ]
    selected, candidates = updater.filter_assets(
        assets, "zip;portable", ["win", "windows"], ["linux", "mac"],
        ["x64", "amd64"], ["arm64", "aarch64", "x86"],
    )
    assert selected["name"] == "tool-windows-x64-portable.zip"
    assert len(candidates) == 1


def test_ambiguous_assets(updater):
    assets = [{"name": "a-portable.zip"}, {"name": "b-portable.zip"}]
    selected, candidates = updater.filter_assets(
        assets, "portable", ["win"], ["linux"], ["x64"], ["arm64"],
    )
    assert selected is None
    assert len(candidates) == 2


def test_process_zip(updater, monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "BASE_DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(updater, "fetch_repo_info", lambda repo: {"description": "example"})
    monkeypatch.setattr(updater, "fetch_latest_release", lambda repo: {
        "assets": [{"name": "example-windows-x64.zip", "browser_download_url": "https://example.invalid/file"}]
    })
    calls = []

    def fake_download(url, dest_path):
        calls.append(url)
        with zipfile.ZipFile(dest_path, "w") as z:
            z.writestr("readme.txt", "ok")

    monkeypatch.setattr(updater, "download_file", fake_download)
    args = ({"repo": "sample/example", "keywords": "zip"}, ["windows"], ["linux"], ["x64"], ["arm64"])
    updater.process_app(*args)
    assert (tmp_path / "example-windows-x64" / "readme.txt").read_text() == "ok"
    assert not (tmp_path / "example-windows-x64.zip").exists()
    updater.process_app(*args)
    assert len(calls) == 1
