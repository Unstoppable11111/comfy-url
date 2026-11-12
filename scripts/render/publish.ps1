<#
推送成图到 GitHub。

    .\publish.ps1                  # 提交所有变更并推送
    .\publish.ps1 "改了什么"        # 自定义提交信息

只推 projects/ 下的图（不动脚本）：
    git add projects; git commit -m "frames"; git push
#>
param([string]$Message = "")

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)

$changed = (git status --porcelain | Measure-Object -Line).Lines
if ($changed -eq 0) {
    Write-Output "没有变更，无需推送"
    exit 0
}

$pngCount = (git status --porcelain | Select-String '\.png$' | Measure-Object).Count
Write-Output "变更 $changed 项，其中图片 $pngCount 张"

if (-not $Message) {
    $Message = "chore: 更新成图 $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git add -A
git commit -q -m $Message
git push origin main 2>&1 | Out-String | Write-Output

Write-Output ("已推送: " + (git log -1 --format='%h %s'))
