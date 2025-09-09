#!/bin/bash
# Script para atualizar o Streamlit Cloud automaticamente

echo "🔄 Atualizando SVB Dashboard no Streamlit Cloud..."

# Adicionar todas as mudanças
git add .

# Pedir descrição da atualização
echo "📝 Digite uma descrição para esta atualização:"
read -r descricao

# Se não digitou nada, usar descrição padrão
if [ -z "$descricao" ]; then
    descricao="Atualização automática $(date +'%d/%m/%Y %H:%M')"
fi

# Fazer commit
git commit -m "$descricao"

# Enviar para GitHub (será configurado em seguida)
echo "📤 Enviando para GitHub..."
git push origin main

echo "✅ Atualização enviada! O Streamlit Cloud será atualizado em 2-3 minutos."
echo "🌐 URL: https://share.streamlit.io/[SEU-USUARIO]/SVB_MVP/main/app.py"
