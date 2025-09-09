@echo off
chcp 65001 >nul
REM Script para atualizar o Streamlit Cloud automaticamente (Windows)

echo 🔄 Atualizando SVB Dashboard no Streamlit Cloud...

REM Verificar se há mudanças para commitar
git status --porcelain >nul
if %errorlevel% neq 0 (
    echo ❌ Erro ao verificar status do Git
    pause
    exit /b 1
)

REM Adicionar todas as mudanças
git add .

REM Verificar se há algo para commitar
for /f %%i in ('git status --porcelain') do set hasChanges=1
if not defined hasChanges (
    echo ℹ️  Não há mudanças para commitar
    echo 🔄 Tentando push mesmo assim...
    git push origin main
    if %errorlevel% equ 0 (
        echo ✅ Push realizado com sucesso!
    ) else (
        echo ❌ Erro no push. Verifique se o repositório GitHub está configurado.
        echo 💡 Execute: git remote add origin https://github.com/SEU-USUARIO/SVB_MVP.git
    )
    pause
    exit /b 0
)

REM Pedir descrição da atualização
set /p descricao="📝 Digite uma descrição para esta atualização (ou Enter para usar padrão): "

REM Se não digitou nada, usar descrição padrão
if "%descricao%"=="" set descricao=Atualização automática %date% %time%

REM Fazer commit
git commit -m "%descricao%"

REM Enviar para GitHub
echo 📤 Enviando para GitHub...
git push origin main

if %errorlevel% equ 0 (
    echo ✅ Atualização enviada! O Streamlit Cloud será atualizado em 2-3 minutos.
    echo 🌐 Acesse sua URL do Streamlit Cloud para ver as mudanças.
) else (
    echo ❌ Erro no push. Verifique se o repositório GitHub está configurado.
    echo 💡 Execute: git remote add origin https://github.com/SEU-USUARIO/SVB_MVP.git
)

pause
