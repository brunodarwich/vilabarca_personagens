$ErrorActionPreference = 'Stop'

# Paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $scriptDir 'run_dashboard.bat'
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'Dashboard de Produção.lnk'

if (-not (Test-Path $batPath)) {
  Write-Error "Arquivo run_dashboard.bat nao encontrado em $scriptDir"
}

# Create WScript.Shell COM object
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($lnkPath)
$Shortcut.TargetPath = $batPath
$Shortcut.WorkingDirectory = $scriptDir
$Shortcut.IconLocation = "$scriptDir\\app.ico,0"
$Shortcut.Description = 'Abrir o Dashboard de Produção (Streamlit)'
$Shortcut.Save()

Write-Host "Atalho criado em: $lnkPath"
