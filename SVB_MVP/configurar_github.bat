@echo off
chcp 65001 >nul
echo 🔧 Configurador GitHub para SVB Dashboard

echo.
echo ⚠️  ATENÇÃO: Você precisa criar o repositório no GitHub primeiro!
echo.
echo 📋 Passos:
echo 1. Acesse: https://github.com
echo 2. Clique em "New repository"
echo 3. Nome: SVB_MVP
echo 4. Tipo: Público
echo 5. NÃO marque "Initialize with README"
echo 6. Clique "Create repository"
echo.

set /p usuario="👤 Digite seu nome de usuário do GitHub: "

if "%usuario%"=="" (
    echo ❌ Nome de usuário é obrigatório!
    pause
    exit /b 1
)

echo.
echo 🔗 Configurando conexão com GitHub...

git remote add origin https://github.com/%usuario%/SVB_MVP.git

if %errorlevel% equ 0 (
    echo ✅ Remote configurado com sucesso!
    echo.
    echo 📤 Enviando código para GitHub...
    git push -u origin main
    
    if %errorlevel% equ 0 (
        echo ✅ Código enviado com sucesso!
        echo.
        echo 🎉 Configuração completa! Agora você pode:
        echo • Usar o script atualizar.bat para atualizações
        echo • Configurar o Streamlit Cloud em: https://share.streamlit.io
        echo • URL do repositório: https://github.com/%usuario%/SVB_MVP
    ) else (
        echo ❌ Erro ao enviar código. Verifique se:
        echo • O repositório foi criado no GitHub
        echo • Você tem permissão de escrita
        echo • Sua autenticação está configurada
    )
) else (
    echo ❌ Erro ao configurar remote
)

echo.
pause
