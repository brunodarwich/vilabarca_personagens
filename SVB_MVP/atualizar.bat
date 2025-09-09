@echo off
REM Script para atualizar o Streamlit Cloud automaticamente (Windows)

echo 🔄 Atualizando SVB Dashboard no Streamlit Cloud...

REM Adicionar todas as mudanças
git add .

REM Pedir descrição da atualização
set /p descricao="📝 Digite uma descrição para esta atualização (ou Enter para usar padrão): "

REM Se não digitou nada, usar descrição padrão
if "%descricao%"=="" set descricao=Atualização automática %date% %time%

REM Fazer commit
git commit -m "%descricao%"

REM Enviar para GitHub
echo 📤 Enviando para GitHub...
git push origin main

echo ✅ Atualização enviada! O Streamlit Cloud será atualizado em 2-3 minutos.
echo 🌐 Acesse sua URL do Streamlit Cloud para ver as mudanças.

pause
