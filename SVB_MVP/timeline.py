"""
Lógica da aba "Histórico": linha do tempo de entregas (Concept / Rig) por personagem.

Exige que o DataFrame tenha as colunas:
- 'Entrega Concept' (texto data) e 'Entrega Rig' (texto data)
- 'Nome do perosnagem', 'ID do Arquivo', 'Episódio'
- Responsáveis e Status de cada etapa
- Links (Concept / Rig)

As datas são parseadas para datetime (naive) com dayfirst=True.
"""
from __future__ import annotations

from typing import Tuple, List
import re
import pandas as pd
import streamlit as st
from datetime import datetime


# Nomes de colunas, iguais aos usados em app.py
COL_EP = 'Episódio'
COL_NAME = 'Nome do perosnagem'
COL_FILE_ID = 'ID do Arquivo'
COL_RIG_LINK = 'Link para baixar o modelo Rigado'
COL_SYNCSKETCH = 'Link do SyncSketch'
COL_CONCEPT_LINK = 'Link para baixar o modelo Ceoncept vetorizado'
COL_STATUS_CONCEPT = 'Status do Concept'
COL_STATUS_RIG = 'Status do Rig'
COL_RESP_CONCEPT = 'Responsável'
COL_RESP_RIG = 'Respondável'
COL_COMMENTS = 'COMENTÁRIOS'
COL_REV_CONCEPT = 'REVISÕES CONCEPT'
COL_REV_RIG = 'REVISÕES RIG'

COL_DATE_CONCEPT = 'Entrega Concept'
COL_DATE_RIG = 'Entrega Rig'
COL_DATE_CONCEPT_DT = 'Entrega Concept (dt)'
COL_DATE_RIG_DT = 'Entrega Rig (dt)'


def _ensure_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    dfx = df.copy()
    if COL_DATE_CONCEPT in dfx.columns and COL_DATE_CONCEPT_DT not in dfx.columns:
        dfx[COL_DATE_CONCEPT_DT] = pd.to_datetime(dfx[COL_DATE_CONCEPT], errors='coerce', dayfirst=True)
    if COL_DATE_RIG in dfx.columns and COL_DATE_RIG_DT not in dfx.columns:
        dfx[COL_DATE_RIG_DT] = pd.to_datetime(dfx[COL_DATE_RIG], errors='coerce', dayfirst=True)
    return dfx


def build_delivery_events(df: pd.DataFrame) -> pd.DataFrame:
    """Gera uma linha por entrega (Concept ou Rig) a partir do DataFrame de produção.

    Columns de saída:
    - date (datetime64), etapa ('Concept'|'Rig'), nome, id, episodio, responsavel, status, link, comments
    - concept_dt (datetime64), rig_dt (datetime64) — para cálculo de delta Concept→Rig
    """
    dfx = _ensure_datetime_columns(df)
    recs: List[dict] = []
    for _, r in dfx.iterrows():
        nome = str(r.get(COL_NAME, ''))
        fid = str(r.get(COL_FILE_ID, ''))
        ep = r.get(COL_EP, '')
        comments = str(r.get(COL_COMMENTS, ''))
        d_c = r.get(COL_DATE_CONCEPT_DT)
        if pd.notna(d_c):
            recs.append({
                'date': pd.to_datetime(d_c),
                'etapa': 'Concept',
                'nome': nome,
                'id': fid,
                'episodio': ep,
                'responsavel': str(r.get(COL_RESP_CONCEPT, '')),
                'status': str(r.get(COL_STATUS_CONCEPT, '')),
                'link': str(r.get(COL_CONCEPT_LINK, '')),
                'sync': str(r.get(COL_SYNCSKETCH, '')),
                'comments': comments,
                'concept_dt': pd.to_datetime(d_c),
                'rig_dt': pd.to_datetime(r.get(COL_DATE_RIG_DT)) if pd.notna(r.get(COL_DATE_RIG_DT)) else pd.NaT,
            })
        d_r = r.get(COL_DATE_RIG_DT)
        if pd.notna(d_r):
            recs.append({
                'date': pd.to_datetime(d_r),
                'etapa': 'Rig',
                'nome': nome,
                'id': fid,
                'episodio': ep,
                'responsavel': str(r.get(COL_RESP_RIG, '')),
                'status': str(r.get(COL_STATUS_RIG, '')),
                'link': str(r.get(COL_RIG_LINK, '')),
                'sync': str(r.get(COL_SYNCSKETCH, '')),
                'comments': comments,
                'concept_dt': pd.to_datetime(d_c) if pd.notna(d_c) else pd.NaT,
                'rig_dt': pd.to_datetime(d_r),
            })
    if not recs:
        return pd.DataFrame(columns=['date','etapa','nome','id','episodio','responsavel','status','link','sync','comments','concept_dt','rig_dt','delta_days'])
    ev = pd.DataFrame.from_records(recs)
    ev['date'] = pd.to_datetime(ev['date']).dt.normalize()
    # Garantir dtype datetime
    ev['concept_dt'] = pd.to_datetime(ev.get('concept_dt'))
    ev['rig_dt'] = pd.to_datetime(ev.get('rig_dt'))
    # Delta em dias (apenas fará sentido para etapa=Rig)
    with pd.option_context('mode.use_inf_as_na', True):
        ev['delta_days'] = (ev['rig_dt'] - ev['concept_dt']).dt.days
    ev.sort_values(['date','etapa','nome'], inplace=True)
    return ev


def render_timeline_tab(df: pd.DataFrame):
    """Renderiza a aba 'Histórico' (linha do tempo de entregas)."""
    st.subheader('Histórico de Entregas — Linha do tempo')
    ev = build_delivery_events(df)
    if ev.empty:
        st.info('Nenhuma entrega encontrada. Preencha as colunas ENTREGA no CSV.')
        return

    # Filtros
    etapas = st.multiselect('Etapas', options=['Concept','Rig'], default=['Concept','Rig'], key='tl_etapas')
    resps = sorted({v for v in ev['responsavel'].dropna().unique().tolist() if str(v).strip()})
    sel_resps = st.multiselect('Responsáveis', options=resps, key='tl_resps')
    q = st.text_input('Buscar por nome ou ID', key='tl_search')

    # Filtro por Episódio (personagens que aparecem no episódio)
    def _parse_eps(val) -> set:
        if val is None:
            return set()
        s = str(val).strip()
        if not s:
            return set()
        if s.lower() == 'todos':
            return {'ALL'}
        return {int(x) for x in re.findall(r"\d+", s)}

    all_eps = sorted({e for v in df.get(COL_EP, []).tolist() for e in _parse_eps(v) if isinstance(e, int)})
    sel_eps = st.multiselect('Episódios', options=all_eps, default=all_eps, key='tl_eps')
    sel_eps_set = set(sel_eps)

    min_d = ev['date'].min()
    max_d = ev['date'].max()
    c1, c2 = st.columns(2)
    default_start = min_d.date() if pd.notna(min_d) else datetime.today().date()
    d_ini = c1.date_input('De', value=default_start, key='tl_date_from')
    default_end = max_d.date() if pd.notna(max_d) else datetime.today().date()
    d_fim = c2.date_input('Até', value=default_end, key='tl_date_to')

    # Aplicar filtros
    fil = ev.copy()
    # Episódio filter on deliveries
    if sel_eps and sel_eps_set and len(sel_eps_set) != 0 and len(sel_eps_set) != len(all_eps):
        mask_ep = fil['episodio'].apply(lambda v: ('ALL' in _parse_eps(v)) or (len(_parse_eps(v) & sel_eps_set) > 0))
        fil = fil[mask_ep]
    if etapas:
        fil = fil[fil['etapa'].isin(etapas)]
    if sel_resps:
        fil = fil[fil['responsavel'].isin(sel_resps)]
    if q:
        qn = str(q).strip().lower()
        fil = fil[(fil['nome'].str.lower().str.contains(qn)) | (fil['id'].str.lower().str.contains(qn))]
    if d_ini:
        fil = fil[fil['date'] >= pd.to_datetime(d_ini)]
    if d_fim:
        fil = fil[fil['date'] <= pd.to_datetime(d_fim)]

    # Gráfico: Linha do tempo com marcações de entregas (por etapa)
    try:
        import altair as alt  # import local
        # Agregar por dia+etapa para termos um ponto por dia, com lista de nomes no tooltip
        agg = (
            fil.groupby(['date', 'etapa'])
               .agg(
                   count=('nome', 'count'),
                   nomes=('nome', lambda s: ', '.join(sorted({str(x) for x in s if str(x).strip()})))
               )
               .reset_index()
        )
        # Construir marcos de revisão (Concept/Rig) como traços verticais
        rev_recs = []
        for _, r in df.iterrows():
            nome = str(r.get(COL_NAME, ''))
            ep_raw = r.get(COL_EP, '')
            # Concept revisions
            raw_c = str(r.get(COL_REV_CONCEPT, '') or '')
            if raw_c.strip():
                for tok in raw_c.replace(',', ';').split(';'):
                    d = pd.to_datetime(tok.strip(), errors='coerce', dayfirst=True)
                    if pd.notna(d):
                        rev_recs.append({
                            'date': pd.to_datetime(d).normalize(),
                            'etapa': 'Concept',
                            'nome': nome,
                            'responsavel': str(r.get(COL_RESP_CONCEPT, '')),
                            'episodio': ep_raw,
                        })
            # Rig revisions
            raw_r = str(r.get(COL_REV_RIG, '') or '')
            if raw_r.strip():
                for tok in raw_r.replace(',', ';').split(';'):
                    d = pd.to_datetime(tok.strip(), errors='coerce', dayfirst=True)
                    if pd.notna(d):
                        rev_recs.append({
                            'date': pd.to_datetime(d).normalize(),
                            'etapa': 'Rig',
                            'nome': nome,
                            'responsavel': str(r.get(COL_RESP_RIG, '')),
                            'episodio': ep_raw,
                        })
        rev = pd.DataFrame.from_records(rev_recs) if rev_recs else pd.DataFrame(columns=['date','etapa','nome','responsavel','episodio'])
        # Aplicar mesmos filtros nas revisões
        if not rev.empty:
            # Episódio filter on revisions
            if sel_eps and sel_eps_set and len(sel_eps_set) != 0 and len(sel_eps_set) != len(all_eps):
                rev = rev[rev['episodio'].apply(lambda v: ('ALL' in _parse_eps(v)) or (len(_parse_eps(v) & sel_eps_set) > 0))]
            if etapas:
                rev = rev[rev['etapa'].isin(etapas)]
            if sel_resps:
                rev = rev[rev['responsavel'].isin(sel_resps)]
            if q:
                qn = str(q).strip().lower()
                rev = rev[rev['nome'].str.lower().str.contains(qn)]
            if d_ini:
                rev = rev[rev['date'] >= pd.to_datetime(d_ini)]
            if d_fim:
                rev = rev[rev['date'] <= pd.to_datetime(d_fim)]
        # Agregar revisões por dia+etapa para tooltip
        rev_agg = (
            rev.groupby(['date','etapa']).agg(
                count=('nome','count'),
                nomes=('nome', lambda s: ', '.join(sorted({str(x) for x in s if str(x).strip()})))
            ).reset_index()
        ) if not rev.empty else pd.DataFrame(columns=['date','etapa','count','nomes'])
        if not agg.empty:
            base = alt.Chart(agg).properties(height=220)
            # Regra horizontal por etapa, do primeiro ao último dia
            rule = (
                base.transform_aggregate(
                        start='min(date)', end='max(date)', groupby=['etapa']
                    )
                    .mark_rule(color='#adb5bd')
                    .encode(
                        y=alt.Y('etapa:N', title='Etapa'),
                        x=alt.X('start:T', title='Data'),
                        x2='end:T'
                    )
            )
            # Marcações (um ponto por dia/etapa), tamanho ~ quantidade
            points = (
                base.mark_circle(opacity=0.9)
                    .encode(
                        x=alt.X('date:T', title='Data'),
                        y=alt.Y('etapa:N', title='Etapa'),
                        color=alt.Color('etapa:N', legend=None),
                        size=alt.Size('count:Q', scale=alt.Scale(range=[40, 400]), legend=alt.Legend(title='Entregas')),
                        tooltip=[
                            alt.Tooltip('date:T', title='Data'),
                            alt.Tooltip('etapa:N', title='Etapa'),
                            alt.Tooltip('count:Q', title='Qtd'),
                            alt.Tooltip('nomes:N', title='Personagens'),
                        ],
                    )
            )
            # Traços verticais para revisões
            rev_layer = alt.Chart(rev_agg).mark_tick(orient='vertical', thickness=2, opacity=0.9).encode(
                x=alt.X('date:T', title='Data'),
                y=alt.Y('etapa:N', title='Etapa'),
                color=alt.Color('etapa:N', legend=None),
                tooltip=[
                    alt.Tooltip('date:T', title='Data'),
                    alt.Tooltip('etapa:N', title='Etapa'),
                    alt.Tooltip('nomes:N', title='Revisões (nomes)')
                ]
            ) if not rev_agg.empty else None
            chart = (rule + points + (rev_layer if rev_layer is not None else base.mark_point(opacity=0))) .interactive()
            st.altair_chart(chart, use_container_width=True)
    except Exception:
        pass

    st.divider()
    # Linha do tempo agrupada por dia, em duas colunas (Concept | Rig)
    for day, grp in fil.groupby('date', sort=True):
        st.markdown(f"### {day.date().strftime('%d/%m/%Y')}")
        col_c, col_r = st.columns(2)
        with col_c:
            st.markdown("**Concept**")
            g_c = grp[grp['etapa'] == 'Concept'].sort_values(['nome'])
            if g_c.empty:
                st.markdown("_Sem entregas de Concept_")
            else:
                for _, r in g_c.iterrows():
                    nm = r['nome']; fid = r['id']; ep = r['episodio']
                    resp = r['responsavel']; status = r['status']
                    link = r['link']; sync = r['sync']; comments = r['comments']
                    links_html = ' '.join([
                        f"<a href='{link}' target='_blank'>Link</a>" if link else '',
                        f"<a href='{sync}' target='_blank'>SyncSketch</a>" if sync else '',
                    ])
                    st.markdown(
                        f"- {nm} <code>{fid}</code> "
                        f"<span style='opacity:0.8'>[Ep: {ep}] • Resp: {resp or '—'} • Status: {status or '—'}</span> "
                        f"{links_html}<br><span style='opacity:0.8'>{comments or ''}</span>",
                        unsafe_allow_html=True,
                    )
        with col_r:
            st.markdown("**Rig**")
            g_r = grp[grp['etapa'] == 'Rig'].sort_values(['nome'])
            if g_r.empty:
                st.markdown("_Sem entregas de Rig_")
            else:
                for _, r in g_r.iterrows():
                    nm = r['nome']; fid = r['id']; ep = r['episodio']
                    resp = r['responsavel']; status = r['status']
                    link = r['link']; sync = r['sync']; comments = r['comments']
                    delta = r.get('delta_days')
                    delta_txt = f" • Tempo Concept→Rig: {int(delta)} dias" if pd.notna(delta) else ''
                    links_html = ' '.join([
                        f"<a href='{link}' target='_blank'>Link</a>" if link else '',
                        f"<a href='{sync}' target='_blank'>SyncSketch</a>" if sync else '',
                    ])
                    st.markdown(
                        f"- {nm} <code>{fid}</code> "
                        f"<span style='opacity:0.8'>[Ep: {ep}] • Resp: {resp or '—'} • Status: {status or '—'}{delta_txt}</span> "
                        f"{links_html}<br><span style='opacity:0.8'>{comments or ''}</span>",
                        unsafe_allow_html=True,
                    )
