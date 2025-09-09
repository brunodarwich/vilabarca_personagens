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
1. Suba este repositório no GitHub (inclua `personagens/` e o CSV)
2. Em https://share.streamlit.io → New app → selecione o repo/branch e `app.py`
3. Deploy

Observações:
- Todos os caminhos são relativos ao diretório do app (compatível com Cloud)
- Certifique-se de que `personagens/` e `SVB_INDEX.xlsx - RIG.csv` estão no repo
