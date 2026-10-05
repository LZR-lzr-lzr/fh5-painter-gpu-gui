"""
FH5 Painter GPU GUI - 带实时进度条与实时预览
@LZR
"""

import os
import re
import shutil
import subprocess
import threading
import queue
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import json
import time
import requests
from pathlib import Path

# 可选：Pillow 用于预览图缩放
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


#============================================================
#下载器
#============================================================
# 可配置的下载源
DOWNLOAD_SOURCES = {
    "exe": {
        # 模型生成器：forza-painter-geometrize-go
        "url": "https://github.com/zjl88858/forza-painter-geometrize-gpu/releases/download/v1.2/forza-painter-geometrize-go.exe",
        "filename": "forza-painter-geometrize-go.exe",
    },
    "painter": {
        # 导入器：forza-painter
        "url": "https://github.com/LZR-lzr-lzr/fh5-painter-gpu-gui/releases/download/Beta_v1.0.1/forza-painter.exe",
        "filename": "forza-painter.exe",
    },
}


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
TEMPLATE_INI["DEFAULT"] = {
    "description": "A good balance of quality and speed",
    "maxPreviewSize": "500",
    "maxResolution": "1200",
    "maxThreads": "0",
    "mutatedSamples": "3000",
    "enableMultiPrimitiveShapes": "false",
    "posterizeLevels": "20",
    "previewEvery": "50",
    "randomSamples": "50000",
    "saveAt": "500,1000,1500,2000,2500,3000",
    "saveEvery": "50",
    "stopAt": "3000",
    "enableProgressiveSampling": "false",
    "progressiveSamplingStart": "10",
    "progressiveSamplingEnd": "1",
    "progressiveSamplingTransition": "0.45",
    "progressiveSamplingCurve": "3",
    "errorGridSize": "64",
}


def check_template_ini(app_self: "App"):
    """检查 settings/template.ini 是否存在，字段是否齐全"""
    os.makedirs(os.path.dirname(SETTINGS_TEMPLATE_INI), exist_ok=True)
    if not os.path.exists(SETTINGS_TEMPLATE_INI):
        with open(SETTINGS_TEMPLATE_INI, "w", encoding="utf-8") as f:
            TEMPLATE_INI.write(f)
        App.log(app_self, f"✅ 已生成 {SETTINGS_TEMPLATE_INI}，请根据需要修改参数")
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
            App.log(app_self, f"✅ 已补充缺失字段: {missing}")
        else:
            App.log(app_self, f"✅ settings/template.ini 字段齐全")
    except Exception as e:
        App.log(app_self, f"❌ 检查 settings/template.ini 时出错: {e}")
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
    nums = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"saveAt 里有非法数字: {token}")
        nums.append(int(token))
    if not nums:
        raise ValueError("saveAt 不能为空")
    return ",".join(str(n) for n in sorted(set(nums)))


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


# ============================================================
# 核心生成逻辑（带实时进度 & 实时预览）
# ============================================================
PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")
SNAPSHOT_RE = re.compile(r"Saved preview snapshot", re.IGNORECASE)


def find_latest_preview(runtime_dir: str, base_name: str):
    """在 runtime 目录里找到最新的 {base_name}_preview*.png"""
    if not os.path.isdir(runtime_dir):
        return None
    latest = None
    latest_mtime = -1
    for f in os.listdir(runtime_dir):
        low = f.lower()
        if not low.endswith(".png"):
            continue
        if not low.startswith(base_name.lower()):
            continue
        if "_preview" not in low:
            continue
        full = os.path.join(runtime_dir, f)
        mtime = os.path.getmtime(full)
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest = full
    return latest


def run_geometrize_gpu(image_path: str,
                       exe_path: str,
                       stop_at: int,
                       save_at: str,
                       save_every: int,
                       json_output_dir: str = None,
                       backend: str = "opencl",
                       log_callback=None,
                       progress_callback=None,
                       preview_callback=None,
                       seed: int = None) -> str:
    """生成 JSON 与预览图"""
    def log(msg):
        if log_callback:
            log_callback(msg)

    if not exe_path or not os.path.exists(exe_path):
        raise FileNotFoundError(f"exe 不存在: {exe_path}")
    log(f"✅ exe: {exe_path}")

    exe_dir = get_exe_dir(exe_path)
    project_root = get_project_root(exe_path)
    settings_dir = get_settings_dir(exe_path)
    base_ini = get_base_ini(exe_path)

    log(f"📂 exe 目录: {exe_dir}")
    log(f"📂 项目根目录: {project_root}")
    log(f"📂 settings: {settings_dir}")
    log(f"📖 基准 ini: {base_ini}")

    if json_output_dir is None:
        json_output_dir = os.path.dirname(os.path.abspath(image_path))
    os.makedirs(json_output_dir, exist_ok=True)
    log(f"📁 输出目录: {json_output_dir}")

    base_name = os.path.splitext(os.path.basename(image_path))[0]

    runtime_dir = os.path.join(script_dir, "runtime")
    os.makedirs(runtime_dir, exist_ok=True)

    custom_ini = os.path.join(runtime_dir, "custom.ini")
    build_custom_ini(base_ini, custom_ini, stop_at, save_at, save_every)
    log(f"📝 已生成 custom.ini")
    log(f"   stopAt    = {stop_at}")
    log(f"   saveAt    = {normalize_save_at(save_at)}")
    log(f"   saveEvery = {save_every}")

    inputs = ["--backend", backend, "-settings", custom_ini]
    if seed is not None:
        inputs += ["-seed", str(seed)]

    tmp_prefix = os.path.join(runtime_dir, base_name)
    inputs += [
        "-output", tmp_prefix,
        "-preview", tmp_prefix + "_preview.png",
        image_path
    ]

    log(f"\n🚀 执行: {exe_path}")
    log(f"📂 工作目录: {project_root}")
    log(f"📦 参数: {inputs}")

    start_time = time.time()

    full_stdout = []
    process = subprocess.Popen(
        [exe_path] + inputs,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
    )

    last_preview_mtime = -1

    for line in process.stdout:
        line = line.rstrip("\r\n")
        if not line:
            continue
        full_stdout.append(line)

        m = PROGRESS_RE.search(line)
        if m and progress_callback:
            try:
                cur = int(m.group(1))
                total = int(m.group(2))
                elapsed = time.time() - start_time
                progress_callback(cur, total, elapsed)
            except ValueError:
                pass

        if SNAPSHOT_RE.search(line) and preview_callback:
            preview_path = find_latest_preview(runtime_dir, base_name)
            if preview_path:
                mtime = os.path.getmtime(preview_path)
                if mtime > last_preview_mtime:
                    last_preview_mtime = mtime
                    preview_callback(preview_path)

        if m:
            cur = int(m.group(1))
            if cur % 50 == 0 or cur == stop_at:
                log(line)

    process.wait()
    log(f"\n📋 返回码: {process.returncode}")

    # ========== 收集结果 ==========
    json_candidates = []
    preview_candidates = []
    for root, dirs, files in os.walk(runtime_dir):
        for f in files:
            full = os.path.join(root, f)
            mtime = os.path.getmtime(full)
            low = f.lower()
            if low.endswith(".json"):
                json_candidates.append((mtime, full, f))
            elif low.endswith("_preview.png"):
                preview_candidates.append((mtime, full, f))

    log(f"\n📊 runtime 里发现: {len(json_candidates)} 个 .json, "
        f"{len(preview_candidates)} 个 _preview.png")

    image_base = os.path.splitext(os.path.basename(image_path))[0]
    final_dir = os.path.join(json_output_dir, f"{image_base}.JsonAndPreview")
    os.makedirs(final_dir, exist_ok=True)
    log(f"📁 输出子目录: {final_dir}")

    # ========== 转换并保留所有 JSON ==========
    for _, src, filename in json_candidates:
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log(f"❌ 读取失败 {filename}: {e}")
            continue

        try:
            converted = json_converter(data)
        except Exception as e:
            log(f"❌ 转换失败 {filename}: {e}")
            continue

        dst = os.path.join(final_dir, filename)
        if os.path.exists(dst):
            os.remove(dst)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(converted)

        try:
            os.remove(src)
        except OSError:
            pass

        log(f"✅ 已转换并保留 JSON: {filename}")

    # 预览图只留最新一张
    if preview_candidates:
        preview_candidates.sort(reverse=True)
        _, src, filename = preview_candidates[0]
        dst = os.path.join(final_dir, filename)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.move(src, dst)
        log(f"✅ 保留预览图: {filename}")
        if len(preview_candidates) > 1:
            log(f"🗑️ 丢弃 {len(preview_candidates) - 1} 张多余预览图")
    else:
        log("⚠️ 没有找到 *_preview.png")

    # 清空 runtime（保留 custom.ini）
    for root, dirs, files in os.walk(runtime_dir):
        for f in files:
            if f == "custom.ini":
                continue
            try:
                os.remove(os.path.join(root, f))
            except OSError:
                pass
    log("🧹 runtime 已清理（custom.ini 保留）")
    log("\n🎉 完成！")
    return "\n".join(full_stdout)


# ============================================================
# converter：FH5-painter 格式 JSON → 紧凑格式
# ============================================================
def json_converter(input_file: dict) -> str:
    if not input_file:
        return ""

    shapes = input_file["shapes"]
    lines = ['{"shapes":']

    for i, shape in enumerate(shapes):
        t = shape["type"]
        d = [int(round(v)) for v in shape["data"]]
        c = [int(v) for v in shape["color"]]
        s = shape["score"]
        tail = "" if i == len(shapes) - 1 else ","
        line = (
            f'{{"type":{t}, "data":{d}, '
            f'"color":{c}, "score":{s}}}{tail}'
        )
        lines.append(line)

    lines.append("]}")
    output = "\n".join(lines)
    print(f"共 {len(shapes)} 个形状")
    return output


# ============================================================
# file_association_manager
# ============================================================
def associate_file_extension(exe_path: str, extension: str):
    """
    用 painter(exe_path) 打开指定的文件(extension)
    :param exe_path:  painter 程序路径
    :param extension: 要打开的文件路径（如 .json）
    """
    if not exe_path or not os.path.exists(exe_path):
        raise FileNotFoundError(f"Painter 不存在: {exe_path}")
    if not extension or not os.path.exists(extension):
        raise FileNotFoundError(f"文件不存在: {extension}")

    subprocess.Popen([exe_path, extension],
                     cwd=os.path.dirname(exe_path))


# ============================================================
# GUI
# ============================================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("FH5 Painter GPU BetaV1.0.1")
        self.root.geometry("1100x860")
        self.root.minsize(1000, 720)

        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.preview_queue = queue.Queue()
        self.is_running = False
        self._preview_image_ref = None

        self.last_output_dir = None

        self._build_ui()
        self._poll_queues()

        self.root.after(200, self._ensure_tools_async)

        self._load_paths_from_ini()
        self._update_json_button_state()

    # ============================ 工具检查 ==========
    def _ensure_tools_async(self):
        """在后台线程里检查和下载，避免卡住 UI"""
        def worker():
            exe, painter = ensure_tools(log_func=self.log)
            if exe and painter:
                # 下载完成后，填到输入框并保存到 ini
                self.root.after(0, lambda: self.var_exe.set(exe))
                self.root.after(0, lambda: self.var_painter.set(painter))
                self.root.after(0, self._update_exe_status)
                self.root.after(0, self._update_painter_status)
            else:
                self.root.after(0, lambda: self.log(
                    "⚠️ 自动下载失败，请手动选择 exe / painter"))

        threading.Thread(target=worker, daemon=True).start()

    # ==================== 初始化 ====================
    def _load_paths_from_ini(self):
        # exe
        exe = load_exe_path()
        if exe:
            self.var_exe.set(exe)
            self.log(f"✅ 从 settings.ini 读到 exePath:")
            self.log(f"   {exe}")
            self._update_exe_status()
        else:
            self.log(f"⚠️ settings.ini 里没有 exePath")
            self.log(f"   请点击「浏览...」选择 exe，然后「💾 保存到 ini」")

        # painter
        painter = load_painter_path()
        if painter:
            self.var_painter.set(painter)
            self.log(f"✅ 从 settings.ini 读到 painterPath:")
            self.log(f"   {painter}")
            self._update_painter_status()
        else:
            self.log(f"⚠️ settings.ini 里没有 painterPath")
            self.log(f"   请点击「浏览...」选择 painter，然后「💾 保存到 ini」")

    # ==================== 构建界面 ====================
    def _build_ui(self):
        # ---------- 顶部：exe 路径 ----------
        frame_exe = ttk.LabelFrame(self.root, text="可执行文件（exePath）")
        frame_exe.pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(frame_exe, text="exe:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_exe = tk.StringVar()
        ttk.Entry(frame_exe, textvariable=self.var_exe).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        ttk.Button(frame_exe, text="浏览...", command=self.pick_exe).grid(
            row=0, column=2, padx=6)
        ttk.Button(frame_exe, text="💾 保存到 ini", command=self.save_exe_to_ini).grid(
            row=0, column=3, padx=6)

        self.lbl_exe_status = ttk.Label(frame_exe, text="", foreground="#666",
                                        wraplength=1040, justify=tk.LEFT)
        self.lbl_exe_status.grid(row=1, column=0, columnspan=4,
                                  sticky=tk.W, padx=6, pady=(0, 4))
        frame_exe.columnconfigure(1, weight=1)

        # ---------- 顶部：painter 路径 ----------
        frame_painter = ttk.LabelFrame(self.root, text="Painter 程序（painterPath）")
        frame_painter.pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(frame_painter, text="painter:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_painter = tk.StringVar()
        ttk.Entry(frame_painter, textvariable=self.var_painter).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        ttk.Button(frame_painter, text="浏览...", command=self.pick_painter).grid(
            row=0, column=2, padx=6)
        ttk.Button(frame_painter, text="💾 保存到 ini", command=self.save_painter_to_ini).grid(
            row=0, column=3, padx=6)

        self.lbl_painter_status = ttk.Label(frame_painter, text="", foreground="#666",
                                            wraplength=1040, justify=tk.LEFT)
        self.lbl_painter_status.grid(row=1, column=0, columnspan=4,
                                     sticky=tk.W, padx=6, pady=(0, 4))
        frame_painter.columnconfigure(1, weight=1)

        # ---------- 主区域：左右分栏 ----------
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        # ---------- 左：参数 ----------
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # 文件
        frame1 = ttk.LabelFrame(left, text="文件路径")
        frame1.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(frame1, text="图片:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_image = tk.StringVar()
        ttk.Entry(frame1, textvariable=self.var_image).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        ttk.Button(frame1, text="浏览...", command=self.pick_image).grid(
            row=0, column=2, padx=6)

        ttk.Label(frame1, text="输出:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_output = tk.StringVar()
        ttk.Entry(frame1, textvariable=self.var_output).grid(
            row=1, column=1, sticky=tk.EW, padx=4, pady=4)
        ttk.Button(frame1, text="浏览...", command=self.pick_output).grid(
            row=1, column=2, padx=6)
        frame1.columnconfigure(1, weight=1)

        # 参数
        frame2 = ttk.LabelFrame(left, text="参数（custom.ini）")
        frame2.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(frame2, text="stopAt:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_stop = tk.StringVar(value="3000")
        ttk.Entry(frame2, textvariable=self.var_stop, width=12).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=4)

        ttk.Label(frame2, text="saveEvery:").grid(row=0, column=2, sticky=tk.W, padx=6, pady=4)
        self.var_every = tk.StringVar(value="100")
        ttk.Entry(frame2, textvariable=self.var_every, width=12).grid(
            row=0, column=3, sticky=tk.W, padx=4, pady=4)

        ttk.Label(frame2, text="backend:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_backend = tk.StringVar(value="opencl")
        ttk.Combobox(frame2, textvariable=self.var_backend,
                     values=["opencl", "vulkan"], width=10, state="readonly").grid(
            row=1, column=1, sticky=tk.W, padx=4, pady=4)

        ttk.Label(frame2, text="saveAt:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_save = tk.StringVar(value="1000,2000,3000")
        ttk.Entry(frame2, textvariable=self.var_save).grid(
            row=2, column=1, columnspan=3, sticky=tk.EW, padx=4, pady=4)
        frame2.columnconfigure(3, weight=1)

        ttk.Label(frame2, text="（逗号分隔；留空则按 saveEvery 自动生成）",
                  foreground="#666").grid(row=3, column=0, columnspan=4,
                                         sticky=tk.W, padx=6, pady=(0, 4))

        # 按钮
        frame3 = ttk.Frame(left)
        frame3.pack(fill=tk.X, pady=4)

        self.btn_run = ttk.Button(frame3, text="🚀 开始生成", command=self.on_run)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        self.btn_open_json = ttk.Button(frame3, text="📂 打开输出",
                                        command=self.open_output)
        self.btn_open_json.pack(side=tk.LEFT, padx=4)

        self.btn_open_painter = ttk.Button(frame3, text="📂 导入JSON(painter引用导入)",
                                           command=self.open_json)
        self.btn_open_painter.pack(side=tk.LEFT, padx=4)
        self.btn_open_painter.config(state=tk.DISABLED)

        self.btn_open_json_inputer = ttk.Button(frame3, text="📂 导入JSON(exe内注入)不可用",
                                           command= lambda: messagebox.showinfo("提示", "此功能暂未实现"))
        self.btn_open_json_inputer.pack(side=tk.LEFT, padx=4)
        self.btn_open_json_inputer.config(state=tk.DISABLED)

        # 进度
        frame_prog = ttk.LabelFrame(left, text="进度")
        frame_prog.pack(fill=tk.X, pady=(6, 6))

        self.lbl_progress = ttk.Label(frame_prog, text="待开始",
                                      font=("Consolas", 10))
        self.lbl_progress.pack(anchor=tk.W, padx=6, pady=(4, 0))

        self.progress = ttk.Progressbar(frame_prog, mode="determinate",
                                        maximum=100, value=0)
        self.progress.pack(fill=tk.X, padx=6, pady=6)

        # 日志
        frame4 = ttk.LabelFrame(left, text="日志")
        frame4.pack(fill=tk.BOTH, expand=True)

        self.txt_log = scrolledtext.ScrolledText(
            frame4, wrap=tk.WORD, height=12, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.txt_log.config(state=tk.DISABLED)

        # ---------- 右：实时预览 ----------
        right = ttk.LabelFrame(main, text="实时预览（最新 preview）")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.lbl_preview = tk.Label(right, text="等待生成...",
                                    bg="#2b2b2b", fg="#888",
                                    font=("微软雅黑", 11))
        self.lbl_preview.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ==================== exe 相关 ====================
    def pick_exe(self):
        current_exe = self.var_exe.get().strip()
        if current_exe and os.path.isdir(os.path.dirname(current_exe)):
            initial = os.path.dirname(current_exe)
        else:
            initial = script_dir

        path = filedialog.askopenfilename(
            title="选择 forza-painter-geometrize-go.exe",
            initialdir=initial,
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
        )
        if path:
            self.var_exe.set(path)
            self._update_exe_status()

    def save_exe_to_ini(self):
        exe = self.var_exe.get().strip()
        if not exe:
            messagebox.showwarning("提示", "请先选择 exe")
            return
        if not os.path.exists(exe):
            messagebox.showerror("错误", f"exe 不存在:\n{exe}")
            return
        try:
            save_exe_path(exe)
            self.log(f"💾 已保存 exePath 到 settings.ini")
            self.log(f"   {exe}")
            messagebox.showinfo("成功", "已保存到 settings.ini")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _update_exe_status(self):
        exe = self.var_exe.get().strip()
        if not exe:
            self.lbl_exe_status.config(text="", foreground="#666")
            return
        if not os.path.exists(exe):
            self.lbl_exe_status.config(text="❌ exe 不存在", foreground="red")
            return
        try:
            base = get_base_ini(exe)
            self.lbl_exe_status.config(
                text=f"✅ 基准 ini: {base}",
                foreground="green"
            )
        except Exception as e:
            self.lbl_exe_status.config(text=f"⚠️ {e}", foreground="orange")

    # ==================== painter 相关 ====================
    def pick_painter(self):
        current = self.var_painter.get().strip()
        if current and os.path.isdir(os.path.dirname(current)):
            initial = os.path.dirname(current)
        else:
            initial = script_dir

        path = filedialog.askopenfilename(
            title="选择 Painter 程序",
            initialdir=initial,
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
        )
        if path:
            self.var_painter.set(path)
            self._update_painter_status()

    def save_painter_to_ini(self):
        painter = self.var_painter.get().strip()
        if not painter:
            messagebox.showwarning("提示", "请先选择 painter")
            return
        if not os.path.exists(painter):
            messagebox.showerror("错误", f"painter 不存在:\n{painter}")
            return
        try:
            save_painter_path(painter)
            self.log(f"💾 已保存 painterPath 到 settings.ini")
            self.log(f"   {painter}")
            messagebox.showinfo("成功", "已保存到 settings.ini")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _update_painter_status(self):
        painter = self.var_painter.get().strip()
        if not painter:
            self.lbl_painter_status.config(text="", foreground="#666")
            return
        if not os.path.exists(painter):
            self.lbl_painter_status.config(text="❌ painter 不存在", foreground="red")
            return
        self.lbl_painter_status.config(
            text=f"✅ painter: {os.path.basename(painter)}",
            foreground="green"
        )

    # ==================== 图片与输出 ====================
    def pick_image(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("所有文件", "*.*")]
        )
        if path:
            self.var_image.set(path)
            self.var_output.set(os.path.dirname(path))

    def pick_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.var_output.set(path)

    def open_output(self):
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            os.startfile(self.last_output_dir)
            return

        out = self.var_output.get().strip()
        if out and os.path.isdir(out):
            os.startfile(out)
            return

        messagebox.showwarning("提示", "输出目录不存在，请先生成一次")

    # ==================== 导入 JSON ====================
    def _update_json_button_state(self):
        """根据当前状态更新「导入JSON」按钮的可用性"""
        if self.is_running:
            self.btn_open_painter.config(state=tk.DISABLED)
            return
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            self.btn_open_painter.config(state=tk.NORMAL)
        else:
            self.btn_open_painter.config(state=tk.DISABLED)

    def open_json(self):
        """从输出目录里选择 JSON，用 painter 打开"""
        painter = self.var_painter.get().strip()
        if not painter or not os.path.exists(painter):
            messagebox.showerror("错误", "请先选择有效的 Painter 程序")
            return

        if not self.last_output_dir or not os.path.isdir(self.last_output_dir):
            messagebox.showwarning("提示", "尚未生成 JSON，请先运行一次生成")
            return

        try:
            json_files = [
                f for f in os.listdir(self.last_output_dir)
                if f.lower().endswith(".json")
            ]
        except OSError as e:
            messagebox.showerror("错误", f"读取输出目录失败: {e}")
            return

        if not json_files:
            messagebox.showwarning("提示", "输出目录里没有 JSON 文件")
            return

        json_files.sort()
        if len(json_files) == 1:
            chosen = json_files[0]
        else:
            chosen = self._pick_json_from_list(json_files)
            if not chosen:
                return

        json_path = os.path.join(self.last_output_dir, chosen)

        try:
            associate_file_extension(painter, json_path)
            self.log(f"📂 已用 Painter 打开: {chosen}")
        except Exception as e:
            messagebox.showerror("错误", f"打开失败: {e}")
            self.log(f"❌ 打开失败: {e}")

    def _pick_json_from_list(self, json_files: list):
        """弹窗让用户从列表里选一个 JSON"""
        result = {"chosen": None}

        win = tk.Toplevel(self.root)
        win.title("选择要导入的 JSON")
        win.geometry("480x400")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="请选择要导入的 JSON 文件：").pack(
            padx=10, pady=(10, 4), anchor=tk.W)

        listbox = tk.Listbox(win, font=("Consolas", 10), selectmode=tk.SINGLE)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        for f in json_files:
            listbox.insert(tk.END, f)
        listbox.selection_set(0)

        def on_ok():
            sel = listbox.curselection()
            if sel:
                result["chosen"] = listbox.get(sel[0])
            win.destroy()

        def on_cancel():
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=6)

        listbox.bind("<Double-Button-1>", lambda e: on_ok())

        self.root.wait_window(win)
        return result["chosen"]

    # ==================== 日志与队列 ====================
    def log(self, msg):
        self.log_queue.put(msg)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """把秒数格式化成 1h2m3s / 2m3s / 3s"""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        m, s = divmod(seconds, 60)
        if m < 60:
            return f"{m}m{s}s"
        h, m = divmod(m, 60)
        return f"{h}h{m}m"

    def _poll_queues(self):
        # 日志
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.txt_log.config(state=tk.NORMAL)
                self.txt_log.insert(tk.END, msg + "\n")
                self.txt_log.see(tk.END)
                self.txt_log.config(state=tk.DISABLED)
        except queue.Empty:
            pass

        # 进度
        try:
            while True:
                cur, total, elapsed = self.progress_queue.get_nowait()
                if total > 0:
                    pct = int(cur * 100 / total)
                    self.progress["value"] = pct

                    used_str = self._fmt_time(elapsed)

                    if cur > 0:
                        per_shape = elapsed / cur
                        remaining = per_shape * (total - cur)
                        remain_str = self._fmt_time(remaining)
                        per_str = f"{per_shape:.3f}s"
                        self.lbl_progress.config(
                            text=f"{cur} / {total}  ({pct}%)   "
                                 f"| 单个 {per_str}   "
                                 f"| 已用 {used_str}   "
                                 f"| 剩余 {remain_str}"
                        )
                    else:
                        self.lbl_progress.config(
                            text=f"{cur} / {total}  ({pct}%)   "
                                 f"| 已用 {used_str}"
                        )
        except queue.Empty:
            pass

        # 预览图
        try:
            while True:
                preview_path = self.preview_queue.get_nowait()
                self._update_preview(preview_path)
        except queue.Empty:
            pass

        self.root.after(80, self._poll_queues)

    def _update_preview(self, img_path):
        """更新 GUI 中的预览图"""
        if not os.path.exists(img_path):
            return
        try:
            if PIL_AVAILABLE:
                from PIL import Image, ImageTk
                img = Image.open(img_path)
                w = self.lbl_preview.winfo_width()
                h = self.lbl_preview.winfo_height()
                if w < 10 or h < 10:
                    w, h = 400, 400
                img.thumbnail((w - 10, h - 10), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(img)
                self._preview_image_ref = tk_img
                self.lbl_preview.config(image=tk_img, text="")
            else:
                tk_img = tk.PhotoImage(file=img_path)
                self._preview_image_ref = tk_img
                self.lbl_preview.config(image=tk_img, text="")
        except Exception as e:
            self.log(f"⚠️ 预览图加载失败: {e}")

    # ==================== 运行 ====================
    def on_run(self):
        if self.is_running:
            messagebox.showinfo("提示", "任务正在进行中...")
            return

        exe = self.var_exe.get().strip()
        if not exe or not os.path.exists(exe):
            messagebox.showerror("错误", "请先选择有效的 exe")
            return

        image = self.var_image.get().strip()
        if not image or not os.path.exists(image):
            messagebox.showerror("错误", "请选择有效的图片")
            return

        output = self.var_output.get().strip()
        if not output:
            output = os.path.dirname(image)
            self.var_output.set(output)

        try:
            stop_at = int(self.var_stop.get().strip())
            save_every = int(self.var_every.get().strip())
        except ValueError:
            messagebox.showerror("错误", "stopAt / saveEvery 必须是整数")
            return

        save_at = self.var_save.get().strip()
        if not save_at:
            save_at = ",".join(str(i) for i in range(save_every, stop_at + 1, save_every))
            self.var_save.set(save_at)

        backend = self.var_backend.get()

        # 重置 UI
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self.lbl_progress.config(text="准备中...")
        self.lbl_preview.config(image="", text="等待生成...")
        self._preview_image_ref = None
        self.last_output_dir = None

        self.is_running = True
        self.btn_run.config(state=tk.DISABLED)
        self._update_json_button_state()

        thread = threading.Thread(
            target=self._worker,
            args=(image, exe, output, stop_at, save_at, save_every, backend),
            daemon=True
        )
        thread.start()

    def _worker(self, image, exe, output, stop_at, save_at, save_every, backend):
        def progress_cb(cur, total, elapsed):
            self.progress_queue.put((cur, total, elapsed))

        def preview_cb(path):
            self.preview_queue.put(path)

        try:
            run_geometrize_gpu(
                image_path=image,
                exe_path=exe,
                stop_at=stop_at,
                save_at=save_at,
                save_every=save_every,
                json_output_dir=output,
                backend=backend,
                log_callback=self.log,
                progress_callback=progress_cb,
                preview_callback=preview_cb
            )

            image_base = os.path.splitext(os.path.basename(image))[0]
            self.last_output_dir = os.path.join(
                output, f"{image_base}.JsonAndPreview")
            self.log(f"\n✅ 全部完成，输出目录: {self.last_output_dir}")

        except Exception as e:
            self.log(f"\n❌ 出错了: {e}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.is_running = False
        self.btn_run.config(state=tk.NORMAL)
        self._update_json_button_state()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.after(0, lambda: check_template_ini(app))
    root.mainloop()