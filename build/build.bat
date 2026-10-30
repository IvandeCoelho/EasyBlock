@echo off
setlocal
REM Vai para a raiz do repositorio (a pasta acima de build\)
cd /d "%~dp0\.."
REM ==========================================================================
REM  build\build.bat - gera dois executaveis em dist\:
REM    dist\EasyBlock.exe       (versao completa, pasta app\)
REM    dist\EasyBlock_Lite.exe  (versao lite, pasta lite\)
REM
REM  Requisitos: Python 3.10+ no PATH.
REM  Assinatura opcional: defina SIGN_PFX e SIGN_PASS antes de rodar.
REM ==========================================================================

echo [1/5] Instalando dependencias...
python -m pip install --upgrade pip || goto :erro
python -m pip install --upgrade psutil pyinstaller || goto :erro

REM Arquivos temporarios do PyInstaller ficam fora do repositorio
set "WORK=%TEMP%\easyblock_build"

echo.
echo [2/5] Gerando EasyBlock.exe (versao completa)...
python -m PyInstaller --noconfirm --clean --onefile --noconsole --uac-admin ^
  --name EasyBlock --distpath dist --workpath "%WORK%" --specpath "%WORK%" ^
  --paths app ^
  --hidden-import core ^
  --hidden-import ui_common ^
  --hidden-import ui_tabs ^
  --hidden-import winreg ^
  app\EasyBlock.py || goto :erro
if not exist dist\EasyBlock.exe (
  echo ERRO: dist\EasyBlock.exe nao foi criado.
  goto :erro
)

echo.
echo [3/5] Gerando EasyBlock_Lite.exe (versao lite)...
python -m PyInstaller --noconfirm --clean --onefile --noconsole --uac-admin ^
  --name EasyBlock_Lite --distpath dist --workpath "%WORK%" --specpath "%WORK%" ^
  lite\EasyBlock_Lite.py || goto :erro
if not exist dist\EasyBlock_Lite.exe (
  echo ERRO: dist\EasyBlock_Lite.exe nao foi criado.
  goto :erro
)

echo.
echo [4/5] Assinatura digital...
if defined SIGN_PFX (
  signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\EasyBlock.exe || goto :erro
  signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\EasyBlock_Lite.exe || goto :erro
  echo Assinados.
) else (
  echo Nao assinados ^(defina SIGN_PFX e SIGN_PASS para assinar^).
)

echo.
echo [5/5] Pronto!
echo Executaveis: %CD%\dist\EasyBlock.exe e %CD%\dist\EasyBlock_Lite.exe
echo.
echo SHA-256 (cole em "sha256" do version.json / version_lite.json):
certutil -hashfile dist\EasyBlock.exe SHA256 | findstr /v ":"
certutil -hashfile dist\EasyBlock_Lite.exe SHA256 | findstr /v ":"
echo.
echo Para o instalador, compile build\installer.iss no Inno Setup 6.
pause
exit /b 0

:erro
echo.
echo *** FALHOU. Veja as mensagens acima. ***
pause
exit /b 1
