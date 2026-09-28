@echo off
setlocal
echo Telechargement de l'installateur officiel Ollama...
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; try { $installerOllama = Join-Path ([System.IO.Path]::GetTempPath()) ('OllamaSetup-' + [guid]::NewGuid().ToString() + '.exe'); Invoke-WebRequest -UseBasicParsing -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $installerOllama; $signatureOllama = Get-AuthenticodeSignature -LiteralPath $installerOllama; if ($signatureOllama.Status -ne 'Valid') { throw 'La signature de l''installateur ne peut pas etre validee. Installation arretee.' }; $processusOllama = Start-Process -FilePath $installerOllama -WindowStyle Normal -Wait -PassThru; if ($processusOllama.ExitCode -ne 0) { throw ('L''installateur a termine avec le code ' + $processusOllama.ExitCode) }; $executableOllama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'; if (-not (Test-Path -LiteralPath $executableOllama)) { throw 'Installation non confirmee a l''emplacement habituel. Verifiez le dossier choisi dans l''assistant.' }; Write-Host 'Ollama est installe. Fermez puis rouvrez PowerShell pour actualiser la commande ollama.'; & $executableOllama --version } catch { Write-Host ('ECHEC : ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo Vous pouvez aussi utiliser https://ollama.com/download/windows
  pause
  exit /b 1
)
echo.
echo Pour le modele de l'exemple, dans un nouveau PowerShell : ollama pull qwen3:4b
pause
