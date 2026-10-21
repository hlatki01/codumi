@echo off
setlocal
set "CODUMI_CLOSE_DIR=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $base=$env:CODUMI_CLOSE_DIR; $targets=@((Join-Path $base 'runtime\pythonw.exe'), (Join-Path $base 'dist\codumi-Windows\runtime\pythonw.exe')); $targets=@($targets | ForEach-Object { [IO.Path]::GetFullPath($_) }); Get-Process -Name pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $targets -icontains $_.Path } | Stop-Process -ErrorAction Stop"
if errorlevel 1 (
  echo Nao foi possivel fechar o codumi. Localize o processo pelo caminho da pasta no Gerenciador de Tarefas.
  pause
  exit /b 1
)
endlocal
