# 🚀 PRÓXIMOS PASSOS - Configuração do GitHub e Streamlit Cloud

## 1. CRIAR REPOSITÓRIO NO GITHUB (5 minutos)

### Passo 1: Acessar GitHub
- Vá para: https://github.com
- Faça login na sua conta (ou crie uma se não tiver)

### Passo 2: Criar novo repositório
- Clique em "New repository" (botão verde)
- Nome do repositório: `SVB_MVP`
- Descrição: "Dashboard SVB - Produção por Episódio"
- Deixe como **PÚBLICO** (para usar o Streamlit Cloud gratuito)
- **NÃO** marque "Add README" (já temos um)
- Clique em "Create repository"

### Passo 3: Copiar URL do repositório
- Copie a URL que aparece (será algo como):
  `https://github.com/SEU-USUARIO/SVB_MVP.git`

## 2. CONECTAR SEU PROJETO AO GITHUB

### No PowerShell (execute na pasta SVB_MVP):
```powershell
# Conectar ao GitHub (substitua pela URL copiada acima)
git remote add origin https://github.com/SEU-USUARIO/SVB_MVP.git

# Renomear branch para main
git branch -M main

# Enviar tudo para o GitHub
git push -u origin main
```

## 3. CONFIGURAR STREAMLIT CLOUD

### Passo 1: Acessar Streamlit Cloud
- Vá para: https://share.streamlit.io
- Clique em "Sign in with GitHub"
- Autorize o Streamlit a acessar seus repositórios

### Passo 2: Criar novo app
- Clique em "New app"
- Repository: selecione `SEU-USUARIO/SVB_MVP`
- Branch: `main`
- Main file path: `app.py`
- Clique em "Deploy!"

### Passo 3: Aguardar deploy
- O deploy demora 2-5 minutos na primeira vez
- Você verá logs de instalação das dependências
- Quando terminar, terá uma URL pública tipo:
  `https://seu-usuario-svb-mvp-app-xyz123.streamlit.app`

## 4. COMO FAZER ATUALIZAÇÕES (rotina diária)

### Opção 1: Script automático (mais fácil)
- Duplo-clique no arquivo `atualizar.bat`
- Digite descrição da mudança
- Pronto! Cloud atualiza em 2-3 minutos

### Opção 2: Comandos manuais
```powershell
git add .
git commit -m "Descrição da mudança"
git push
```

## 5. COMPARTILHAMENTO

### Para sua equipe:
- Compartilhe apenas a URL do Streamlit Cloud
- Eles acessam direto no navegador
- Sempre veem a versão mais atual automaticamente
- Não precisam instalar nada

## ✅ CHECKLIST FINAL

- [ ] Repositório criado no GitHub
- [ ] Código enviado com `git push`
- [ ] App criado no Streamlit Cloud
- [ ] URL funcionando
- [ ] Teste de atualização feito
- [ ] URL compartilhada com a equipe

## 🆘 TROUBLESHOOTING

### Se der erro no git push:
```powershell
# Configurar credenciais (se pedido)
git config --global credential.helper manager-core
```

### Se o app não carregar no Cloud:
- Verifique se todos os arquivos foram para o GitHub
- Confirme que `requirements.txt` está correto
- Veja os logs na interface do Streamlit Cloud

### Se as imagens não aparecerem:
- Confirme que a pasta `personagens/` está no GitHub
- Verifique se os arquivos começam com `SVB_`
