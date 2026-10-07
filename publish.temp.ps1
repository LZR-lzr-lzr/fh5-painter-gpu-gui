# publish.ps1 - 设置 token 并一键发布

$ErrorActionPreference = "Stop"

# 切到脚本所在目录
Set-Location -Path $PSScriptRoot

# ====================
# 把下面的 token 换成你自己的
$env:GITHUB_TOKEN = "github_pat_你的实际token"

if (-not $env:GITHUB_TOKEN -or $env:GITHUB_TOKEN -like "*你的实际token*") {
    Write-Host "❌ 请先在 publish.ps1 里填入真实的 GITHUB_TOKEN" -ForegroundColor Red
    exit 1
}

Write-Host "GITHUB_TOKEN 已设置" -ForegroundColor Green

# ====================
foreach ($name in @("build", "dist")) {
    $path = Join-Path $PSScriptRoot $name
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
        Write-Host "已清理: $name" -ForegroundColor DarkGray
    }
}

# ========== 3. 运行 publish.py ==========
Write-Host "开始发布..." -ForegroundColor Cyan
python publish.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ publish.py 返回非零退出码: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "发布完成" -ForegroundColor Green