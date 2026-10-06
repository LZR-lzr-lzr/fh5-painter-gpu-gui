"""
gpu_geometrize.py - geometrize 调用、JSON 转换、文件关联、进程树控制
"""

import os
import re
import json
import time
import shutil
import threading
import subprocess

from tools import (
    script_dir,
    get_exe_dir,
    get_project_root,
    get_settings_dir,
    get_base_ini,
    read_ini,
    set_ini_value,
    normalize_save_at,
    build_custom_ini,
)


PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")
SNAPSHOT_RE = re.compile(r"Saved preview snapshot", re.IGNORECASE)


# ============================================================
# 当前子进程管理（用于关闭 GUI / 暂停 / 恢复 / 终止）
# ============================================================
_current_process = None
_current_process_lock = threading.Lock()


def _set_current_process(p):
    global _current_process
    with _current_process_lock:
        _current_process = p


def get_current_process():
    with _current_process_lock:
        return _current_process


def kill_current_process_tree(timeout: float = 3.0):
    """
    终止当前 geometrize 进程及其子进程树。
    优先用 psutil；未安装则退回 Windows 的 taskkill /T /F。
    未在运行时安全返回。
    """
    p = get_current_process()
    if p is None or p.poll() is not None:
        return

    # 1) 优先 psutil，能精确杀整棵进程树
    try:
        import psutil
        try:
            proc = psutil.Process(p.pid)
        except psutil.NoSuchProcess:
            return
        children = proc.children(recursive=True)
        for c in children:
            try:
                c.kill()
            except Exception:
                pass
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            pass
        return
    except ImportError:
        pass

    # 2) 兜底：Windows 的 taskkill /T /F 能杀进程树
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                capture_output=True, timeout=timeout + 2,
            )
            return
        except Exception:
            pass

    # 3) 最后的兜底：直接 kill
    try:
        p.kill()
    except Exception:
        pass


def pause_current_process_tree() -> bool:
    """
    暂停当前 geometrize 进程及其子进程。
    依赖 psutil；未安装或失败时返回 False。
    """
    p = get_current_process()
    if p is None or p.poll() is not None:
        return False

    try:
        import psutil
    except ImportError:
        return False

    try:
        proc = psutil.Process(p.pid)
    except psutil.NoSuchProcess:
        return False

    ok = False
    # 先暂停子进程，再暂停父进程
    try:
        for c in proc.children(recursive=True):
            try:
                c.suspend()
                ok = True
            except Exception:
                pass
        try:
            proc.suspend()
            ok = True
        except Exception:
            pass
    except Exception:
        return False

    return ok


def resume_current_process_tree() -> bool:
    """
    恢复当前 geometrize 进程及其子进程。
    依赖 psutil；未安装或失败时返回 False。
    """
    p = get_current_process()
    if p is None or p.poll() is not None:
        return False

    try:
        import psutil
    except ImportError:
        return False

    try:
        proc = psutil.Process(p.pid)
    except psutil.NoSuchProcess:
        return False

    ok = False
    # 先恢复父进程，再恢复子进程
    try:
        try:
            proc.resume()
            ok = True
        except Exception:
            pass
        for c in proc.children(recursive=True):
            try:
                c.resume()
                ok = True
            except Exception:
                pass
    except Exception:
        return False

    return ok


# ============================================================
# 预览图查找
# ============================================================
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


# ============================================================
# 核心：调用 geometrize 生成 JSON 与预览图
# ============================================================
def run_geometrize_gpu(image_path: str,
                       exe_path: str,
                       stop_at: int,
                       save_at: str,
                       save_every: int,
                       json_output_dir: str = None,
                       backend: str = "openCL",
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

    inputs = ["-backend", backend, "-settings", custom_ini]
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
    _set_current_process(process)

    try:
        # 进程若在短时间内就退出且返回码非 0，直接抛错，避免"沉默卡住"
        time.sleep(0.5)
        if process.poll() is not None and process.returncode != 0:
            rest = ""
            try:
                if process.stdout is not None:
                    rest = process.stdout.read() or ""
            except Exception:
                pass
            if rest:
                for ln in rest.splitlines():
                    log(ln)
            raise RuntimeError(
                f"渲染器启动即退出 (returncode={process.returncode})。\n"
                f"可能是 backend='{backend}' 不被支持，或缺少对应的 GPU 运行时。\n"
                f"参数: {inputs}"
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
    finally:
        _set_current_process(None)

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