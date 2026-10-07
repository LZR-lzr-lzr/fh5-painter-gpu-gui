#=============================================================
#APP 配置文件
#=============================================================

VERSION = "1.1.1-Beta"
APP_NAME = "FH5 Painter GPU"

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

DEFAULT_INI = {
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
# ============================================================
# 多语言字典
# 想加语言：在 LANG 里加一项；再到 LANG_NAMES 里加显示名即可
# 占位符用 {xxx}，调用 tr("key", xxx=value) 传入
# ============================================================
LANG_DEFAULT = "zh_CN"

LANG = {
    "zh_CN": {
        "app_title": f"{APP_NAME} {VERSION}",
        "label_language": "语言:",

        # exe 区域
        "frame_exe": "可执行文件（exePath）",
        "label_exe": "exe:",
        "btn_browse": "浏览...",
        "btn_save_ini": "💾 保存到 ini",

        # painter 区域
        "frame_painter": "Painter 程序（painterPath）",
        "label_painter": "painter:",

        # 文件
        "frame_files": "文件路径",
        "label_image": "图片:",
        "label_output": "输出:",

        # 参数
        "frame_params": "参数（custom.ini）",
        "label_stop_at": "stopAt:",
        "label_save_every": "saveEvery:",
        "label_backend": "backend:",
        "label_save_at": "saveAt:",
        "hint_save_at": "（逗号分隔；留空则按 saveEvery 自动生成）",

        # 按钮
        "btn_run": "🚀 开始生成",
        "btn_pause": "⏸️ 暂停",
        "btn_resume": "▶️ 继续",
        "btn_open_output": "📂 打开输出",
        "btn_import_json_painter": "📂 导入JSON(painter引用导入)",
        "btn_import_json_exe": "📂 导入JSON(exe内注入)不可用",

        # 进度
        "frame_progress": "进度",
        "label_progress_init": "待开始",
        "label_progress_preparing": "准备中...",

        # 日志
        "frame_log": "日志",

        # 预览
        "frame_preview": "实时预览（最新 preview）",
        "label_preview_wait": "等待生成...",

        # 状态标签
        "status_exe_missing": "❌ exe 不存在",
        "status_painter_missing": "❌ painter 不存在",
        "status_base_ini": "✅ 基准 ini: {path}",
        "status_base_ini_error": "⚠️ {err}",
        "status_painter": "✅ painter: {name}",

        # messagebox 标题
        "msg_title_hint": "提示",
        "msg_title_error": "错误",
        "msg_title_success": "成功",

        # messagebox 内容
        "msg_pick_exe_first": "请先选择 exe",
        "msg_exe_not_exist": "exe 不存在:\n{path}",
        "msg_saved_ini": "已保存到 settings.ini",
        "msg_save_failed": "保存失败: {err}",
        "msg_pick_painter_first": "请先选择 painter",
        "msg_painter_not_exist": "painter 不存在:\n{path}",
        "msg_output_not_exist": "输出目录不存在，请先生成一次",
        "msg_pick_valid_painter": "请先选择有效的 Painter 程序",
        "msg_no_json_generated": "尚未生成 JSON，请先运行一次生成",
        "msg_read_output_failed": "读取输出目录失败: {err}",
        "msg_no_json_in_output": "输出目录里没有 JSON 文件",
        "msg_open_failed": "打开失败: {err}",
        "msg_task_running": "任务正在进行中...",
        "msg_pick_valid_exe": "请先选择有效的 exe",
        "msg_pick_valid_image": "请选择有效的图片",
        "msg_int_required": "stopAt / saveEvery 必须是整数",
        "msg_not_implemented": "此功能暂未实现",
        "msg_confirm_exit_running": "任务正在运行，确定要退出并终止后台进程吗？",
        "msg_pause_failed": "暂停失败（可能未安装 psutil，请执行 pip install psutil）",
        "msg_resume_failed": "继续失败（可能未安装 psutil）",

        # JSON 选择对话框
        "dialog_pick_json_title": "选择要导入的 JSON",
        "dialog_pick_json_prompt": "请选择要导入的 JSON 文件：",
        "dialog_btn_ok": "确定",
        "dialog_btn_cancel": "取消",
    },

    "zh_TW": {
        "app_title": f"{APP_NAME} {VERSION}",
        "label_language": "語言:",

        "frame_exe": "可執行檔（exePath）",
        "label_exe": "exe:",
        "btn_browse": "瀏覽...",
        "btn_save_ini": "💾 儲存到 ini",

        "frame_painter": "Painter 程式（painterPath）",
        "label_painter": "painter:",

        "frame_files": "檔案路徑",
        "label_image": "圖片:",
        "label_output": "輸出:",

        "frame_params": "參數（custom.ini）",
        "label_stop_at": "stopAt:",
        "label_save_every": "saveEvery:",
        "label_backend": "backend:",
        "label_save_at": "saveAt:",
        "hint_save_at": "（逗號分隔；留空則依 saveEvery 自動產生）",

        "btn_run": "🚀 開始產生",
        "btn_pause": "⏸️ 暫停",
        "btn_resume": "▶️ 繼續",
        "btn_open_output": "📂 開啟輸出",
        "btn_import_json_painter": "📂 匯入JSON(painter引用匯入)",
        "btn_import_json_exe": "📂 匯入JSON(exe內注入)不可用",

        "frame_progress": "進度",
        "label_progress_init": "待開始",
        "label_progress_preparing": "準備中...",

        "frame_log": "日誌",

        "frame_preview": "即時預覽（最新 preview）",
        "label_preview_wait": "等待產生...",

        "status_exe_missing": "❌ exe 不存在",
        "status_painter_missing": "❌ painter 不存在",
        "status_base_ini": "✅ 基準 ini: {path}",
        "status_base_ini_error": "⚠️ {err}",
        "status_painter": "✅ painter: {name}",

        "msg_title_hint": "提示",
        "msg_title_error": "錯誤",
        "msg_title_success": "成功",

        "msg_pick_exe_first": "請先選擇 exe",
        "msg_exe_not_exist": "exe 不存在:\n{path}",
        "msg_saved_ini": "已儲存到 settings.ini",
        "msg_save_failed": "儲存失敗: {err}",
        "msg_pick_painter_first": "請先選擇 painter",
        "msg_painter_not_exist": "painter 不存在:\n{path}",
        "msg_output_not_exist": "輸出目錄不存在，請先產生一次",
        "msg_pick_valid_painter": "請先選擇有效的 Painter 程式",
        "msg_no_json_generated": "尚未產生 JSON，請先執行一次產生",
        "msg_read_output_failed": "讀取輸出目錄失敗: {err}",
        "msg_no_json_in_output": "輸出目錄裡沒有 JSON 檔案",
        "msg_open_failed": "開啟失敗: {err}",
        "msg_task_running": "任務正在進行中...",
        "msg_pick_valid_exe": "請先選擇有效的 exe",
        "msg_pick_valid_image": "請選擇有效的圖片",
        "msg_int_required": "stopAt / saveEvery 必須是整數",
        "msg_not_implemented": "此功能尚未實作",
        "msg_confirm_exit_running": "任務正在運行，確定要退出並終止後台進程嗎？",
        "msg_pause_failed": "暫停失敗（可能未安裝 psutil，請執行 pip install psutil）",
        "msg_resume_failed": "繼續失敗（可能未安裝 psutil）",

        "dialog_pick_json_title": "選擇要匯入的 JSON",
        "dialog_pick_json_prompt": "請選擇要匯入的 JSON 檔案：",
        "dialog_btn_ok": "確定",
        "dialog_btn_cancel": "取消",
    },

    "en": {
        "app_title": f"{APP_NAME} {VERSION}",
        "label_language": "Language:",

        "frame_exe": "Executable (exePath)",
        "label_exe": "exe:",
        "btn_browse": "Browse...",
        "btn_save_ini": "💾 Save to ini",

        "frame_painter": "Painter App (painterPath)",
        "label_painter": "painter:",

        "frame_files": "File Paths",
        "label_image": "Image:",
        "label_output": "Output:",

        "frame_params": "Parameters (custom.ini)",
        "label_stop_at": "stopAt:",
        "label_save_every": "saveEvery:",
        "label_backend": "backend:",
        "label_save_at": "saveAt:",
        "hint_save_at": "(comma-separated; leave blank to auto-generate by saveEvery)",

        "btn_run": "🚀 Start",
        "btn_pause": "⏸️ Pause",
        "btn_resume": "▶️ Resume",
        "btn_open_output": "📂 Open Output",
        "btn_import_json_painter": "📂 Import JSON (via Painter)",
        "btn_import_json_exe": "📂 Import JSON (exe inject) N/A",

        "frame_progress": "Progress",
        "label_progress_init": "Ready",
        "label_progress_preparing": "Preparing...",

        "frame_log": "Log",

        "frame_preview": "Live Preview (latest)",
        "label_preview_wait": "Waiting...",

        "status_exe_missing": "❌ exe not found",
        "status_painter_missing": "❌ painter not found",
        "status_base_ini": "✅ Base ini: {path}",
        "status_base_ini_error": "⚠️ {err}",
        "status_painter": "✅ painter: {name}",

        "msg_title_hint": "Info",
        "msg_title_error": "Error",
        "msg_title_success": "Success",

        "msg_pick_exe_first": "Please select exe first",
        "msg_exe_not_exist": "exe not found:\n{path}",
        "msg_saved_ini": "Saved to settings.ini",
        "msg_save_failed": "Save failed: {err}",
        "msg_pick_painter_first": "Please select painter first",
        "msg_painter_not_exist": "painter not found:\n{path}",
        "msg_output_not_exist": "Output directory does not exist. Run generation first.",
        "msg_pick_valid_painter": "Please select a valid Painter program first",
        "msg_no_json_generated": "No JSON generated yet. Run generation first.",
        "msg_read_output_failed": "Failed to read output directory: {err}",
        "msg_no_json_in_output": "No JSON files in output directory",
        "msg_open_failed": "Open failed: {err}",
        "msg_task_running": "A task is already running...",
        "msg_pick_valid_exe": "Please select a valid exe",
        "msg_pick_valid_image": "Please select a valid image",
        "msg_int_required": "stopAt / saveEvery must be integers",
        "msg_not_implemented": "This feature is not implemented yet",
        "msg_confirm_exit_running": "A task is running. Exit and terminate the background process?",
        "msg_pause_failed": "Pause failed (psutil may be missing: pip install psutil)",
        "msg_resume_failed": "Resume failed (psutil may be missing)",

        "dialog_pick_json_title": "Select JSON to import",
        "dialog_pick_json_prompt": "Select a JSON file to import:",
        "dialog_btn_ok": "OK",
        "dialog_btn_cancel": "Cancel",
    },
}

# 语言显示名（顺序即下拉框显示顺序）
LANG_NAMES = {
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "en": "English",
}