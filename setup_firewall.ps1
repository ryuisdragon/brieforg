#!/usr/bin/env powershell
<#
.SYNOPSIS
    設置 Windows 防火牆規則，允許 Python 應用程序通過端口 8000

.DESCRIPTION
    此腳本會創建防火牆規則，允許 Python 應用程序通過端口 8000 進行入站和出站連接
    這對於讓其他設備能夠連接到您的企劃分析服務是必要的

.PARAMETER Port
    要開放的端口號，預設為 8000

.EXAMPLE
    .\setup_firewall.ps1
    .\setup_firewall.ps1 -Port 8000
#>

param(
    [int]$Port = 8000
)

# 檢查是否以管理員權限運行
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ 此腳本需要管理員權限才能設置防火牆規則" -ForegroundColor Red
    Write-Host "💡 請右鍵點擊 PowerShell 並選擇 '以系統管理員身分執行'" -ForegroundColor Yellow
    exit 1
}

Write-Host "🔧 設置 Windows 防火牆規則" -ForegroundColor Green
Write-Host "📡 端口: $Port" -ForegroundColor Cyan
Write-Host "=" * 50

try {
    # 檢查規則是否已存在
    $existingRule = Get-NetFirewallRule -DisplayName "企劃分析服務 - 端口 $Port" -ErrorAction SilentlyContinue
    
    if ($existingRule) {
        Write-Host "⚠️  防火牆規則已存在，正在更新..." -ForegroundColor Yellow
        Remove-NetFirewallRule -DisplayName "企劃分析服務 - 端口 $Port" -ErrorAction SilentlyContinue
    }
    
    # 創建入站規則
    Write-Host "📥 創建入站規則..." -ForegroundColor Cyan
    New-NetFirewallRule -DisplayName "企劃分析服務 - 端口 $Port" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any `
        -Description "允許企劃分析服務通過端口 $Port 的入站連接"
    
    # 創建出站規則
    Write-Host "📤 創建出站規則..." -ForegroundColor Cyan
    New-NetFirewallRule -DisplayName "企劃分析服務 - 端口 $Port (出站)" `
        -Direction Outbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any `
        -Description "允許企劃分析服務通過端口 $Port 的出站連接"
    
    Write-Host "✅ 防火牆規則設置完成！" -ForegroundColor Green
    Write-Host "🌐 其他設備現在可以通過以下地址訪問您的服務：" -ForegroundColor Cyan
    
    # 獲取本機 IP 地址
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
    
    if ($localIP) {
        Write-Host "   http://$localIP`:$Port" -ForegroundColor White
        Write-Host "   http://$localIP`:$Port/docs" -ForegroundColor White
    }
    else {
        Write-Host "   無法獲取本機 IP 地址" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "💡 提示：" -ForegroundColor Yellow
    Write-Host "   1. 確保後端服務正在運行 (python start_server.py)" -ForegroundColor White
    Write-Host "   2. 其他設備需要與您的電腦在同一個網路中" -ForegroundColor White
    Write-Host "   3. 如果仍有問題，請檢查路由器設置" -ForegroundColor White
    
}
catch {
    Write-Host "❌ 設置防火牆規則失敗: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "💡 請手動檢查 Windows Defender 防火牆設置" -ForegroundColor Yellow
    exit 1
} 