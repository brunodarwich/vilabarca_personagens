# SVB Dashboard (Streamlit)

Dashboard de produção por episódio usando Streamlit.

## Estrutura
- `app.py`: app principal
- `list_tab.py`, `timeline.py`, `stats.py`: módulos auxiliares
- `personagens/`: imagens (SVB_*.png)
- `SVB_INDEX.xlsx - RIG.csv`: dados principais
- `.streamlit/config.toml`: tema
- `requirements.txt`: dependências

## Rodar localmente
1. Python 3.10–3.12
2. `pip install -r requirements.txt`
3. `streamlit run app.py`

## Publicar no Streamlit Community Cloud

### 1. Preparar o repositório GitHub
```bash
# No PowerShell, dentro da pasta SVB_MVP
git init
git add .
git commit -m "SVB dashboard - deploy inicial"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SVB_MVP.git
git push -u origin main
```

### 2. Deploy no Streamlit Cloud
1. Acesse: https://share.streamlit.io
2. Sign in com GitHub
3. Clique em "New app"
4. Selecione:
   - Repository: `SEU_USUARIO/SVB_MVP`
   - Branch: `main`
   - Main file path: `app.py`
5. Clique em "Deploy!"

### 3. Verificações pós-deploy
- ✅ CSV carregado: verifique que `SVB_INDEX.xlsx - RIG.csv` está no repo
- ✅ Imagens aparecendo: confirme que a pasta `personagens/` está no repo
- ✅ Funcionalidades: teste filtros, abas e exportação PNG

### Troubleshooting
- **ModuleNotFoundError**: Verifique se todas as dependências estão em `requirements.txt`
- **CSV não encontrado**: Certifique-se que o arquivo está na raiz do repo
- **Imagens não aparecem**: Verifique se a pasta `personagens/` foi incluída no commit

## Observações técnicas
- Todos os caminhos são relativos ao diretório do app (compatível com Cloud)
- Imports robustos com fallbacks para módulos opcionais
- Cache otimizado para performance no Cloud
