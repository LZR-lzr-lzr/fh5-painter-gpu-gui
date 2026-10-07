"""
main.py - FH5 Painter GPU GUI
@LZR
"""

import os
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from tools import (
    script_dir,
    check_template_ini,
    ensure_tools,
    load_exe_path,
    save_exe_path,
    load_painter_path,
    save_painter_path,
    get_base_ini,
    load_custom_ini_params,
)
from gpu_geometrize import (
    run_geometrize_gpu,
    associate_file_extension,
    kill_current_process_tree,
    pause_current_process_tree,
    resume_current_process_tree,
)

import app_config

LANG = app_config.LANG
LANG_NAMES = app_config.LANG_NAMES
_current_lang = app_config.LANG_DEFAULT


def tr(key: str, **fmt) -> str:
    """取当前语言的文本；带占位符时做格式化"""
    table = LANG.get(_current_lang) or LANG["zh_CN"]
    text = table.get(key)
    if text is None:
        # 找不到时回退到 zh_CN，再回退到 key 本身
        text = LANG["zh_CN"].get(key, key)
    if fmt:
        try:
            return text.format(**fmt)
        except Exception:
            return text
    return text


def set_language(code: str) -> bool:
    """切换当前语言；成功返回 True"""
    global _current_lang
    if code in LANG:
        _current_lang = code
        return True
    return False


# ============================================================
# GUI
# ============================================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title(tr("app_title"))
        self.root.geometry("1100x880")
        self.root.minsize(1000, 720)

        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.preview_queue = queue.Queue()
        self.is_running = False
        self.is_paused = False
        self._preview_image_ref = None
        self._tr_registry = []  # [(widget, option, lang_key), ...]

        self.last_output_dir = None

        self._build_ui()
        self._poll_queues()

        self.root.after(200, self._ensure_tools_async)

        self._load_paths_from_ini()
        self._load_custom_params()
        self._update_action_buttons()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================== 多语言辅助 ====================
    def _reg(self, widget, key: str, option: str = "text"):
        """把控件登记到多语言表，立即用当前语言设置文本；返回 widget 便于链式调用"""
        try:
            widget.configure(**{option: tr(key)})
        except Exception:
            pass
        self._tr_registry.append((widget, option, key))
        return widget

    def _retranslate(self):
        """切换语言后刷新所有已登记控件 + 状态标签"""
        self.root.title(tr("app_title"))
        for widget, option, key in self._tr_registry:
            try:
                widget.configure(**{option: tr(key)})
            except Exception:
                pass
        # 暂停按钮的文本是动态的，单独刷新
        self._update_pause_button_text()
        # 状态标签里含拼接内容，重新计算一次
        self._update_exe_status()
        self._update_painter_status()

    def _on_lang_change(self, event=None):
        name = self.var_lang.get()
        for code, n in LANG_NAMES.items():
            if n == name:
                if set_language(code):
                    self._retranslate()
                break

    # ============================ 工具检查 ==========
    def _ensure_tools_async(self):
        """在后台线程里检查和下载，避免卡住 UI"""
        def worker():
            exe, painter = ensure_tools(log_func=self.log)
            if exe and painter:
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
    
        # ==================== 参数加载 ====================
    def _load_custom_params(self):
        """优先从 runtime/custom.ini 读参数填充 UI；没有则保持默认值"""
        params = load_custom_ini_params()
        if not params:
            return

        if "stopAt" in params:
            self.var_stop.set(params["stopAt"])
        if "saveAt" in params:
            self.var_save.set(params["saveAt"])
        if "saveEvery" in params:
            self.var_every.set(params["saveEvery"])

        self.log("📄 已从 runtime/custom.ini 载入参数")
        self.log(f"   stopAt    = {params.get('stopAt', '(默认)')}")
        self.log(f"   saveAt    = {params.get('saveAt', '(默认)')}")
        self.log(f"   saveEvery = {params.get('saveEvery', '(默认)')}")

    # ==================== 窗口关闭 ====================
    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno(
                tr("msg_title_hint"),
                tr("msg_confirm_exit_running"),
            ):
                return
        try:
            kill_current_process_tree()
        except Exception as e:
            self.log(f"⚠️ 终止后台进程失败: {e}")
        self.root.destroy()

    # ==================== 暂停 / 继续 ====================
    def _update_pause_button_text(self):
        """根据暂停状态刷新按钮文本"""
        if self.is_paused:
            self.btn_pause.config(text=tr("btn_resume"))
        else:
            self.btn_pause.config(text=tr("btn_pause"))

    def _on_pause_resume(self):
        if not self.is_running:
            return
        if self.is_paused:
            if resume_current_process_tree():
                self.is_paused = False
                self._update_pause_button_text()
                self.log("▶️ 已继续")
            else:
                messagebox.showerror(tr("msg_title_error"),
                                     tr("msg_resume_failed"))
        else:
            if pause_current_process_tree():
                self.is_paused = True
                self._update_pause_button_text()
                self.log("⏸️ 已暂停")
            else:
                messagebox.showerror(tr("msg_title_error"),
                                     tr("msg_pause_failed"))

    # ==================== 构建界面 ====================
    def _build_ui(self):
        # ---------- 顶部：语言选择 ----------
        frame_lang = ttk.Frame(self.root)
        frame_lang.pack(fill=tk.X, padx=10, pady=(6, 0))

        self.lbl_language = self._reg(ttk.Label(frame_lang, text=""), "label_language")
        self.lbl_language.pack(side=tk.LEFT, padx=(0, 4))

        self.var_lang = tk.StringVar(value=LANG_NAMES[_current_lang])
        self.combo_lang = ttk.Combobox(
            frame_lang,
            textvariable=self.var_lang,
            values=list(LANG_NAMES.values()),
            width=14,
            state="readonly",
        )
        self.combo_lang.pack(side=tk.LEFT)
        self.combo_lang.bind("<<ComboboxSelected>>", self._on_lang_change)

        # ---------- 顶部：exe 路径 ----------
        frame_exe = self._reg(ttk.LabelFrame(self.root, text=""), "frame_exe")
        frame_exe.pack(fill=tk.X, padx=10, pady=6)

        self._reg(ttk.Label(frame_exe, text=""), "label_exe").grid(
            row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_exe = tk.StringVar()
        ttk.Entry(frame_exe, textvariable=self.var_exe).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        self._reg(ttk.Button(frame_exe, text="", command=self.pick_exe),
                  "btn_browse").grid(row=0, column=2, padx=6)
        self._reg(ttk.Button(frame_exe, text="", command=self.save_exe_to_ini),
                  "btn_save_ini").grid(row=0, column=3, padx=6)

        self.lbl_exe_status = ttk.Label(frame_exe, text="", foreground="#666",
                                        wraplength=1040, justify=tk.LEFT)
        self.lbl_exe_status.grid(row=1, column=0, columnspan=4,
                                  sticky=tk.W, padx=6, pady=(0, 4))
        frame_exe.columnconfigure(1, weight=1)

        # ---------- 顶部：painter 路径 ----------
        frame_painter = self._reg(ttk.LabelFrame(self.root, text=""), "frame_painter")
        frame_painter.pack(fill=tk.X, padx=10, pady=6)

        self._reg(ttk.Label(frame_painter, text=""), "label_painter").grid(
            row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_painter = tk.StringVar()
        ttk.Entry(frame_painter, textvariable=self.var_painter).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        self._reg(ttk.Button(frame_painter, text="", command=self.pick_painter),
                  "btn_browse").grid(row=0, column=2, padx=6)
        self._reg(ttk.Button(frame_painter, text="", command=self.save_painter_to_ini),
                  "btn_save_ini").grid(row=0, column=3, padx=6)

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
        frame1 = self._reg(ttk.LabelFrame(left, text=""), "frame_files")
        frame1.pack(fill=tk.X, pady=(0, 6))

        self._reg(ttk.Label(frame1, text=""), "label_image").grid(
            row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_image = tk.StringVar()
        ttk.Entry(frame1, textvariable=self.var_image).grid(
            row=0, column=1, sticky=tk.EW, padx=4, pady=4)
        self._reg(ttk.Button(frame1, text="", command=self.pick_image),
                  "btn_browse").grid(row=0, column=2, padx=6)

        self._reg(ttk.Label(frame1, text=""), "label_output").grid(
            row=1, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_output = tk.StringVar()
        ttk.Entry(frame1, textvariable=self.var_output).grid(
            row=1, column=1, sticky=tk.EW, padx=4, pady=4)
        self._reg(ttk.Button(frame1, text="", command=self.pick_output),
                  "btn_browse").grid(row=1, column=2, padx=6)
        frame1.columnconfigure(1, weight=1)

        # 参数
        frame2 = self._reg(ttk.LabelFrame(left, text=""), "frame_params")
        frame2.pack(fill=tk.X, pady=(0, 6))

        self._reg(ttk.Label(frame2, text=""), "label_stop_at").grid(
            row=0, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_stop = tk.StringVar(value="3000")
        ttk.Entry(frame2, textvariable=self.var_stop, width=12).grid(
            row=0, column=1, sticky=tk.W, padx=4, pady=4)

        self._reg(ttk.Label(frame2, text=""), "label_save_every").grid(
            row=0, column=2, sticky=tk.W, padx=6, pady=4)
        self.var_every = tk.StringVar(value="100")
        ttk.Entry(frame2, textvariable=self.var_every, width=12).grid(
            row=0, column=3, sticky=tk.W, padx=4, pady=4)

        self._reg(ttk.Label(frame2, text=""), "label_backend").grid(
            row=1, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_backend = tk.StringVar(value="openCL")
        ttk.Combobox(frame2, textvariable=self.var_backend,
                     values=["openCL", "Vulkan"], width=10, state="readonly").grid(
            row=1, column=1, sticky=tk.W, padx=4, pady=4)

        self._reg(ttk.Label(frame2, text=""), "label_save_at").grid(
            row=2, column=0, sticky=tk.W, padx=6, pady=4)
        self.var_save = tk.StringVar(value="1000,2000,3000")
        ttk.Entry(frame2, textvariable=self.var_save).grid(
            row=2, column=1, columnspan=3, sticky=tk.EW, padx=4, pady=4)
        frame2.columnconfigure(3, weight=1)

        hint = self._reg(ttk.Label(frame2, text="", foreground="#666"), "hint_save_at")
        hint.grid(row=3, column=0, columnspan=4, sticky=tk.W, padx=6, pady=(0, 4))

        # 按钮
        frame3 = ttk.Frame(left)
        frame3.pack(fill=tk.X, pady=4)

        self.btn_run = self._reg(
            ttk.Button(frame3, text="", command=self.on_run), "btn_run")
        self.btn_run.pack(side=tk.LEFT, padx=4)

        # 暂停/继续按钮（动态文本，不注册到 _tr_registry，由 _update_pause_button_text 统一管理）
        self.btn_pause = ttk.Button(
            frame3, text=tr("btn_pause"), command=self._on_pause_resume)
        self.btn_pause.pack(side=tk.LEFT, padx=4)
        self.btn_pause.config(state=tk.DISABLED)

        self.btn_open_json = self._reg(
            ttk.Button(frame3, text="", command=self.open_output), "btn_open_output")
        self.btn_open_json.pack(side=tk.LEFT, padx=4)

        self.btn_open_painter = self._reg(
            ttk.Button(frame3, text="", command=self.open_json),
            "btn_import_json_painter")
        self.btn_open_painter.pack(side=tk.LEFT, padx=4)
        self.btn_open_painter.config(state=tk.DISABLED)

        self.btn_open_json_inputer = self._reg(
            ttk.Button(
                frame3, text="",
                command=lambda: messagebox.showinfo(
                    tr("msg_title_hint"), tr("msg_not_implemented")),
            ),
            "btn_import_json_exe",
        )
        self.btn_open_json_inputer.pack(side=tk.LEFT, padx=4)
        self.btn_open_json_inputer.config(state=tk.DISABLED)

        # 进度
        frame_prog = self._reg(ttk.LabelFrame(left, text=""), "frame_progress")
        frame_prog.pack(fill=tk.X, pady=(6, 6))

        self.lbl_progress = ttk.Label(frame_prog, text=tr("label_progress_init"),
                                      font=("Consolas", 10))
        self.lbl_progress.pack(anchor=tk.W, padx=6, pady=(4, 0))

        self.progress = ttk.Progressbar(frame_prog, mode="determinate",
                                        maximum=100, value=0)
        self.progress.pack(fill=tk.X, padx=6, pady=6)

        # 日志
        frame4 = self._reg(ttk.LabelFrame(left, text=""), "frame_log")
        frame4.pack(fill=tk.BOTH, expand=True)

        self.txt_log = scrolledtext.ScrolledText(
            frame4, wrap=tk.WORD, height=12, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.txt_log.config(state=tk.DISABLED)

        # ---------- 右：实时预览 ----------
        right = self._reg(ttk.LabelFrame(main, text=""), "frame_preview")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.lbl_preview = tk.Label(right, text=tr("label_preview_wait"),
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
            messagebox.showwarning(tr("msg_title_hint"), tr("msg_pick_exe_first"))
            return
        if not os.path.exists(exe):
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_exe_not_exist", path=exe))
            return
        try:
            save_exe_path(exe)
            self.log(f"💾 已保存 exePath 到 settings.ini")
            self.log(f"   {exe}")
            messagebox.showinfo(tr("msg_title_success"), tr("msg_saved_ini"))
        except Exception as e:
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_save_failed", err=e))

    def _update_exe_status(self):
        exe = self.var_exe.get().strip()
        if not exe:
            self.lbl_exe_status.config(text="", foreground="#666")
            return
        if not os.path.exists(exe):
            self.lbl_exe_status.config(text=tr("status_exe_missing"),
                                       foreground="red")
            return
        try:
            base = get_base_ini(exe)
            self.lbl_exe_status.config(
                text=tr("status_base_ini", path=base),
                foreground="green"
            )
        except Exception as e:
            self.lbl_exe_status.config(
                text=tr("status_base_ini_error", err=e),
                foreground="orange"
            )

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
            messagebox.showwarning(tr("msg_title_hint"), tr("msg_pick_painter_first"))
            return
        if not os.path.exists(painter):
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_painter_not_exist", path=painter))
            return
        try:
            save_painter_path(painter)
            self.log(f"💾 已保存 painterPath 到 settings.ini")
            self.log(f"   {painter}")
            messagebox.showinfo(tr("msg_title_success"), tr("msg_saved_ini"))
        except Exception as e:
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_save_failed", err=e))

    def _update_painter_status(self):
        painter = self.var_painter.get().strip()
        if not painter:
            self.lbl_painter_status.config(text="", foreground="#666")
            return
        if not os.path.exists(painter):
            self.lbl_painter_status.config(text=tr("status_painter_missing"),
                                           foreground="red")
            return
        self.lbl_painter_status.config(
            text=tr("status_painter", name=os.path.basename(painter)),
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

        messagebox.showwarning(tr("msg_title_hint"), tr("msg_output_not_exist"))

    # ==================== 导入 JSON ====================
    def _update_action_buttons(self):
        """根据当前状态刷新「暂停」「导入JSON」按钮的可用性"""
        # 暂停按钮：只在任务进行中可用
        if self.is_running:
            self.btn_pause.config(state=tk.NORMAL)
        else:
            self.btn_pause.config(state=tk.DISABLED)

        # 导入 JSON 按钮：任务结束且输出目录存在时可用
        if self.is_running:
            self.btn_open_painter.config(state=tk.DISABLED)
            return
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            self.btn_open_painter.config(state=tk.NORMAL)
        else:
            self.btn_open_painter.config(state=tk.DISABLED)

    def open_json(self):
        painter = self.var_painter.get().strip()
        if not painter or not os.path.exists(painter):
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_pick_valid_painter"))
            return

        if not self.last_output_dir or not os.path.isdir(self.last_output_dir):
            messagebox.showwarning(tr("msg_title_hint"),
                                   tr("msg_no_json_generated"))
            return

        try:
            json_files = [
                f for f in os.listdir(self.last_output_dir)
                if f.lower().endswith(".json")
            ]
        except OSError as e:
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_read_output_failed", err=e))
            return

        if not json_files:
            messagebox.showwarning(tr("msg_title_hint"),
                                   tr("msg_no_json_in_output"))
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
            messagebox.showerror(tr("msg_title_error"),
                                 tr("msg_open_failed", err=e))
            self.log(f"❌ 打开失败: {e}")

    def _pick_json_from_list(self, json_files: list):
        result = {"chosen": None}

        win = tk.Toplevel(self.root)
        win.title(tr("dialog_pick_json_title"))
        win.geometry("480x400")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text=tr("dialog_pick_json_prompt")).pack(
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
        ttk.Button(btn_frame, text=tr("dialog_btn_ok"),
                   command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text=tr("dialog_btn_cancel"),
                   command=on_cancel).pack(side=tk.LEFT, padx=6)

        listbox.bind("<Double-Button-1>", lambda e: on_ok())

        self.root.wait_window(win)
        return result["chosen"]

    # ==================== 日志与队列 ====================
    def log(self, msg):
        self.log_queue.put(msg)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
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
            messagebox.showinfo(tr("msg_title_hint"), tr("msg_task_running"))
            return

        exe = self.var_exe.get().strip()
        if not exe or not os.path.exists(exe):
            messagebox.showerror(tr("msg_title_error"), tr("msg_pick_valid_exe"))
            return

        image = self.var_image.get().strip()
        if not image or not os.path.exists(image):
            messagebox.showerror(tr("msg_title_error"), tr("msg_pick_valid_image"))
            return

        output = self.var_output.get().strip()
        if not output:
            output = os.path.dirname(image)
            self.var_output.set(output)

        try:
            stop_at = int(self.var_stop.get().strip())
            save_every = int(self.var_every.get().strip())
        except ValueError:
            messagebox.showerror(tr("msg_title_error"), tr("msg_int_required"))
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
        self.lbl_progress.config(text=tr("label_progress_preparing"))
        self.lbl_preview.config(image="", text=tr("label_preview_wait"))
        self._preview_image_ref = None
        self.last_output_dir = None

        self.is_paused = False
        self._update_pause_button_text()

        self.is_running = True
        self.btn_run.config(state=tk.DISABLED)
        self._update_action_buttons()

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
            if not self.root.winfo_exists():
                return
            self.log(f"\n❌ 出错了: {e}")
            self.log(traceback.format_exc())
        finally:
            if self.root.winfo_exists():
                self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.is_running = False
        self.is_paused = False
        self._update_pause_button_text()
        self.btn_run.config(state=tk.NORMAL)
        self._update_action_buttons()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.after(0, lambda: check_template_ini(app.log))
    root.mainloop()