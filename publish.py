
import os
import re
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

import requests
import app_config


# ============================================================
# 配置
# ============================================================
OWNER = app_config.OWNER
REPO = app_config.REPO
TAG_PREFIX = app_config.TAG_PREFIX
DRAFT = app_config.DRAFT
PRERELEASE = app_config.PRERELEASE

ROOT = Path(__file__).parent.resolve()
RELEASE_DIR = ROOT / "release"
UPDATE_MD = ROOT / "update.md"
APP_CONFIG = ROOT / "app_config.py"
ENTRY = "main.py"


# ============================================================
# 工具函数
# ============================================================
def log(msg: str):
    print(f"[publish] {msg}")


def read_version() -> str:
    return app_config.VERSION


def run(cmd: list, **kwargs):
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


# ============================================================
# 步骤 1：PyInstaller 打包
# ============================================================
def build_exe():
    log("步骤 1/5：PyInstaller 打包...")

    # 清理旧产物
    for d in ("build", "dist"):
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "FH5Painter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--collect-data", "certifi",
        ENTRY,
    ]
    run(cmd, cwd=str(ROOT))

    # 产物通常在 dist/FH5Painter.exe
    exe = ROOT / "dist" / "FH5Painter.exe"
    if not exe.exists():
        # 兼容大小写
        for f in (ROOT / "dist").iterdir():
            if f.suffix.lower() == ".exe":
                exe = f
                break
    if not exe.exists():
        raise FileNotFoundError("PyInstaller 没有生成 exe")
    return exe


# ============================================================
# 步骤 2：重命名并放到 release/
# ============================================================
def rename_and_move(exe: Path, version: str) -> Path:
    log("步骤 2/5：重命名并移动到 release/...")
    RELEASE_DIR.mkdir(exist_ok=True)

    target_name = f"FH5 Painter {version}.onefile.exe"
    target = RELEASE_DIR / target_name

    if target.exists():
        target.unlink()
    shutil.move(str(exe), str(target))
    log(f"  → {target}")
    return target


# ============================================================
# 步骤 3：创建 7z 和 zip
# ============================================================
def make_7z(src: Path) -> Path:
    log("步骤 3a/5：创建 .7z...")
    dst = src.with_suffix(".7z")
    if dst.exists():
        dst.unlink()

    # 优先用 py7zr
    try:
        import py7zr
        with py7zr.SevenZipFile(dst, "w") as z:
            z.write(src, arcname=src.name)
        log(f"  → {dst}")
        return dst
    except ImportError:
        pass

    # 退回 7z 命令行（需要 7-Zip 已安装且加入 PATH）
    seven = shutil.which("7z") or shutil.which("7za")
    if not seven:
        raise RuntimeError(
            "创建 7z 失败：既没装 py7zr，也找不到 7z 命令行。\n"
            "  解决方案一：pip install py7zr\n"
            "  解决方案二：安装 7-Zip 并把安装目录加入 PATH"
        )
    run([seven, "a", "-t7z", str(dst), str(src)], cwd=str(src.parent))
    log(f"  → {dst}")
    return dst


def make_zip(src: Path) -> Path:
    log("步骤 3b/5：创建 .zip...")
    dst = src.with_suffix(".zip")
    if dst.exists():
        dst.unlink()
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(src, arcname=src.name)
    log(f"  → {dst}")
    return dst


# ============================================================
# 步骤 4：读取 update.md
# ============================================================
def read_release_notes() -> str:
    log("步骤 4/5：读取 update.md...")
    if not UPDATE_MD.exists():
        log("  ⚠️ 找不到 update.md，使用空说明")
        return ""
    return UPDATE_MD.read_text(encoding="utf-8")


# ============================================================
# 步骤 5：GitHub API 发布
# ============================================================
def gh_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def create_release(token: str, tag: str, name: str, body: str) -> dict:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": DRAFT,
        "prerelease": PRERELEASE,
    }
    log(f"  创建 release: tag={tag}")
    r = requests.post(url, headers=gh_headers(token), json=payload, timeout=60)

    if r.status_code == 422:
        # tag 已存在，提示用户
        raise RuntimeError(
            f"创建失败（422）：tag '{tag}' 可能已存在。\n"
            f"  请先在 GitHub 上删除该 release/tag，或修改 app_config.py 的 VERSION。\n"
            f"  响应: {r.text}"
        )
    r.raise_for_status()
    return r.json()


def upload_asset(token: str, upload_url: str, file: Path):
    # upload_url 形如 https://uploads.github.com/repos/.../assets{?name,label}
    base = upload_url.split("{")[0]
    url = f"{base}?name={requests.utils.quote(file.name)}"

    log(f"  上传资产: {file.name} ({file.stat().st_size / 1024 / 1024:.1f} MB)")
    with open(file, "rb") as f:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            },
            data=f,
            timeout=600,
        )
    r.raise_for_status()
    return r.json()


def publish(token: str, version: str, files: list):
    log("步骤 5/5：发布到 GitHub Release...")
    tag = f"{TAG_PREFIX}{version}"
    name = f"FH5 Painter GPU {version}"
    body = read_release_notes()

    release = create_release(token, tag, name, body)
    log(f"  ✅ Release: {release['html_url']}")

    upload_url = release["upload_url"]
    for f in files:
        upload_asset(token, upload_url, f)

    log(f"  ✅ 所有资产已上传")


# ============================================================
# 主流程
# ============================================================
def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("❌ 请先设置环境变量 GITHUB_TOKEN")
        print("   PowerShell: $env:GITHUB_TOKEN=\"ghp_xxx\"")
        print("   CMD:        set GITHUB_TOKEN=ghp_xxx")
        sys.exit(1)

    version = read_version()
    log(f"检测到 VERSION = {version}")

    exe = build_exe()
    exe_renamed = rename_and_move(exe, version)
    exe_7z = make_7z(exe_renamed)
    exe_zip = make_zip(exe_renamed)

    publish(token, version, [exe_renamed, exe_7z, exe_zip])

    log("🎉 全部完成")


if __name__ == "__main__":
    main()