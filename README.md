# FH5 Painter GPU GUI

A simple GUI for generating Forza Horizon 5 vinyl groups using
`forza-painter-geometrize-go`.

一个用于生成《极限竞速：地平线 5》涂装的图形界面工具，底层调用
`forza-painter-geometrize-go`。

- `forza-painter-geometrize-go` 来自 @zjl88858
  https://github.com/zjl88858/forza-painter-geometrize-gpu

---

## Features / 功能

- Simple graphical interface / 简洁的图形界面
- Adjustable `stopAt` / `saveAt` / `saveEvery` / 可调整的形状数量与快照参数
- Real-time progress bar / 实时进度条
- Live preview of the latest snapshot / 实时预览最新快照
- Configurable exe path via `settings.ini` / 通过 `settings.ini` 配置 exe 路径
- All JSON files are kept, only the latest preview is kept / 所有 JSON 均保留，预览图只留最新一张

---

## How to use / 使用方法

1. Download the files / 先下载文件。

### Onefile version / 打包版本

- Open `FH5Painter.onefile.exe` / 打开 `FH5Painter.onefile.exe`

### Python version / Python 文件

- Run `use_powershell.py` with VS Code / 使用 VS Code 运行

### Attention / 注意事项

- The `vulkan` mode in the GUI does not work. Use PowerShell instead.
  GUI 中的 `vulkan` 模式无效，请改用 PowerShell 调用。

```powershell
.\dist\forza-painter-geometrize-go.exe `
    --backend vulkan `
    -output "C:/to/input" `
    -preview "C:/to/preview.png" `
    "C:/to/input.png"
```    

## Screenshots / 应用图片
![GUI 截图](docs/src1.png)
![GUI 准备好截图](docs/src0.png)
![GUI 生成时截图](docs/src2.png)