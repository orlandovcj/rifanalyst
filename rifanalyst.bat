@echo off
title RIFAnalyst v3.6 - Analisador de RIF/COAF
setlocal

:: Configuração de cores para facilitar a leitura (Texto verde)
color 0A

echo =========================================================
echo       INICIANDO RIFAnalyst v3.6 - NAE/CGU/SC
echo =========================================================
echo.

:: 1. Verificação de Dependências
echo [1/2] Verificando e instalando bibliotecas necessarias...
if exist requirements.txt (
    pip install -r requirements.txt --quiet --disable-pip-version-check
    echo [OK] Dependencias verificadas com sucesso.
) else (
    echo [!] AVISO: requirements.txt nao encontrado. 
    echo Tentando iniciar com as bibliotecas locais...
)

echo.

:: 2. Execução do Sistema
echo [2/2] Abrindo interface do Streamlit...
echo.
streamlit run main.py

:: Mantém o terminal aberto caso ocorra erro crítico no código
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Ocorreu um erro critico ao rodar o RIFAnalyst.
    echo Verifique se o Python e o Streamlit estão no PATH do Windows.
    pause
)

endlocal