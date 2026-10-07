"""
tools.py - 路径常量、settings.ini 读写、ini 操作、自动下载
"""

import os
import re
import sys
import configparser
from pathlib import Path

import requests
import app_config


# ============================================================
# 下载器
# ============================================================
# 可配置的下载源
DOWNLOAD_SOURCES = app_config.DOWNLOAD_SOURCES


def download_file(url: str, save_path: str, log_func=print) -> bool:
    """从 URL 下载文件，带进度提示"""
    try:
        log_func(f"⬇️ 正在下载: {url}")
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        done = 0

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if total > 0 and done % (1024 * 1024) < 8192:
                        pct = done * 100 // total
                        log_func(f"   {pct}% ({done // 1024} KB / {total // 1024} KB)")

        log_func(f"✅ 已下载: {save_path}")
        return True

    except Exception as e:
        log_func(f"❌ 下载失败: {e}")
        return False


def ensure_tools(log_func=print) -> tuple:
    """
    检查 exe 和 painter 是否存在于程序目录，不存在就自动下载。
    :return: (exe_path, painter_path)，失败返回 (None, None)
    """
    exe_path = os.path.join(script_dir, DOWNLOAD_SOURCES["exe"]["filename"])
    painter_path = os.path.join(script_dir, DOWNLOAD_SOURCES["painter"]["filename"])

    # 检查 exe
    if not os.path.exists(exe_path):
        log_func(f"⚠️ 未找到 {os.path.basename(exe_path)}，开始下载...")
        if not download_file(DOWNLOAD_SOURCES["exe"]["url"], exe_path, log_func):
            return None, None

    # 检查 painter
    if not os.path.exists(painter_path):
        log_func(f"⚠️ 未找到 {os.path.basename(painter_path)}，开始下载...")
        if not download_file(DOWNLOAD_SOURCES["painter"]["url"], painter_path, log_func):
            return None, None

    return exe_path, painter_path


# ============================================================
# 路径常量
# ============================================================
def get_app_dir() -> str:
    """
    获取应用所在目录：
    - 打包后（PyInstaller）：exe 所在目录
    - 未打包：脚本所在目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


script_dir = get_app_dir()
SETTINGS_INI = os.path.join(script_dir, "settings.ini")
SETTINGS_TEMPLATE_INI = os.path.join(script_dir, "settings", "template.ini")


# ============================================================
# settings 检查
# ============================================================
TEMPLATE_INI: configparser.ConfigParser = configparser.ConfigParser()
TEMPLATE_INI.optionxform = str
TEMPLATE_INI["DEFAULT"] = app_config.DEFAULT_INI


def check_template_ini(log_func=print):
    """检查 settings/template.ini 是否存在，字段是否齐全"""
    os.makedirs(os.path.dirname(SETTINGS_TEMPLATE_INI), exist_ok=True)
    if not os.path.exists(SETTINGS_TEMPLATE_INI):
        with open(SETTINGS_TEMPLATE_INI, "w", encoding="utf-8") as f:
            TEMPLATE_INI.write(f)
        log_func(f"✅ 已生成 {SETTINGS_TEMPLATE_INI}，请根据需要修改参数")
        return

    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(SETTINGS_TEMPLATE_INI, encoding="utf-8")
        missing = []
        for key in TEMPLATE_INI["DEFAULT"]:
            if not cfg.has_option(configparser.DEFAULTSECT, key):
                cfg.set(configparser.DEFAULTSECT, key,
                        TEMPLATE_INI["DEFAULT"][key])
                missing.append(key)
        if missing:
            with open(SETTINGS_TEMPLATE_INI, "w", encoding="utf-8") as f:
                cfg.write(f)
            log_func(f"✅ 已补充缺失字段: {missing}")
        else:
            log_func(f"✅ settings/template.ini 字段齐全")
    except Exception as e:
        log_func(f"❌ 检查 settings/template.ini 时出错: {e}")


# ============================================================
# settings.ini 读写
# ============================================================
def _clean_path(raw: str) -> str:
    s = raw.strip()
    if s.startswith(("r'", 'r"', "R'", 'R"')):
        s = s[1:]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s.strip()


def _load_path_from_ini(key_names: list, ini_path: str = SETTINGS_INI) -> str:
    """通用：从 settings.ini 读取某个 key 的值"""
    if not os.path.exists(ini_path):
        return ""
    raw = None
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(ini_path, encoding="utf-8")
        for section in cfg.sections() + [configparser.DEFAULTSECT]:
            for key in key_names:
                if cfg.has_option(section, key):
                    raw = cfg.get(section, key)
                    break
            if raw:
                break
    except Exception:
        pass
    if not raw:
        lower_keys = [k.lower() for k in key_names]
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                lower_line = line.lower()
                for lk in lower_keys:
                    if lower_line.startswith(lk):
                        _, _, value = line.partition("=")
                        raw = value
                        break
                if raw:
                    break
    if not raw:
        return ""
    return _clean_path(raw)


def _save_path_to_ini(key: str, value: str, ini_path: str = SETTINGS_INI):
    """通用：把某个 key 写回 settings.ini（保留其他字段）"""
    lines = []
    if os.path.exists(ini_path):
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.IGNORECASE)
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key} = {value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key} = {value}\n")
    os.makedirs(os.path.dirname(ini_path), exist_ok=True)
    with open(ini_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def load_exe_path(ini_path: str = SETTINGS_INI) -> str:
    return _load_path_from_ini(["exePath", "exepath", "ExePath", "EXEPATH"], ini_path)


def save_exe_path(exe_path: str, ini_path: str = SETTINGS_INI):
    _save_path_to_ini("exePath", exe_path, ini_path)


def load_painter_path(ini_path: str = SETTINGS_INI) -> str:
    return _load_path_from_ini(
        ["painterPath", "painterpath", "PainterPath", "PAINTERPATH"], ini_path)


def save_painter_path(painter_path: str, ini_path: str = SETTINGS_INI):
    _save_path_to_ini("painterPath", painter_path, ini_path)


# ============================================================
# 从 exe 推导路径
# ============================================================
def get_exe_dir(exe_path: str) -> str:
    return os.path.dirname(os.path.abspath(exe_path))


def get_project_root(exe_path: str) -> str:
    return os.path.dirname(get_exe_dir(exe_path))


def get_settings_dir(exe_path: str) -> str:
    exe_dir = get_exe_dir(exe_path)
    candidates = [
        os.path.join(exe_dir, "settings"),
        os.path.join(os.path.dirname(exe_dir), "settings"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    raise FileNotFoundError(
        f"找不到 settings 目录。已尝试:\n  " + "\n  ".join(candidates)
    )


def get_base_ini(exe_path: str) -> str:
    settings_dir = get_settings_dir(exe_path)
    for name in ["c.ini", "_default.ini", "template.ini"]:
        p = os.path.join(settings_dir, name)
        if os.path.exists(p):
            return p
    for f in sorted(os.listdir(settings_dir)):
        if f.lower().endswith(".ini"):
            return os.path.join(settings_dir, f)
    raise FileNotFoundError(f"{settings_dir} 里没有任何 .ini 文件")


# ============================================================
# ini 读写
# ============================================================
def read_ini(ini_path: str) -> list:
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"找不到基准配置文件: {ini_path}")
    with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def set_ini_value(lines: list, key: str, value: str) -> list:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.IGNORECASE)
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key} = {value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key} = {value}\n")
    return new_lines


def normalize_save_at(value: str) -> str:
    # 1. 只允许数字和分隔符
    for token in value:
        if token not in "0123456789,， \t":
            raise ValueError(f"saveAt 里有非法字符: {token}")

    # 2. 统一分隔符为半角逗号
    normalized = value.replace("，", ",").replace(" ", ",").replace("\t", ",")

    # 3. 切分并过滤空段
    tokens = [t for t in normalized.split(",") if t]

    if not tokens:
        raise ValueError("saveAt 不能为空")

    # 4. 转成 int 做数值排序 + 去重
    nums = sorted({int(t) for t in tokens})

    return ",".join(str(n) for n in nums)


def build_custom_ini(src_path: str, dst_path: str,
                     stop_at: int, save_at: str, save_every: int) -> str:
    lines = read_ini(src_path)
    save_at_norm = normalize_save_at(save_at)
    lines = set_ini_value(lines, "stopAt", str(stop_at))
    lines = set_ini_value(lines, "saveAt", save_at_norm)
    lines = set_ini_value(lines, "saveEvery", str(save_every))
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return dst_path


def load_custom_ini_params(ini_path: str = None) -> dict:
    """
    读取 runtime/custom.ini 里的参数（stopAt / saveAt / saveEvery）。
    文件不存在或读不到字段时返回空 dict。
    """
    if ini_path is None:
        ini_path = os.path.join(script_dir, "runtime", "custom.ini")
    if not os.path.exists(ini_path):
        return {}

    keys = ("stopAt", "saveAt", "saveEvery")
    patterns = {
        k: re.compile(rf"^\s*{re.escape(k)}\s*=\s*(.*)$", re.IGNORECASE)
        for k in keys
    }
    result = {}
    try:
        with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                for k, pat in patterns.items():
                    if k in result:
                        continue
                    m = pat.match(line)
                    if m:
                        val = m.group(1).strip()
                        if val:
                            result[k] = val
    except Exception:
        pass
    return result