"""
Lógica da aba "Lista": sintetiza demandas em progresso, pendentes de revisão e não iniciadas
para Concept e Rig, com filtros simples.
"""
from __future__ import annotations

import re
import io
import base64
from typing import List, Tuple, Callable, Optional
import textwrap
import pandas as pd
import streamlit as st
try:
    from unidecode import unidecode
except ImportError:
    # Fallback se unidecode não estiver disponível
    def unidecode(s):
        return s
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageFont

# Nomes de colunas (iguais aos usados em app.py / timeline.py)
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


def _norm(s: str) -> str:
    # Normaliza para ascii sem acentos e remove não alfanuméricos
    return re.sub(r"[^a-z0-9]+", "", unidecode(str(s or "").strip().lower()))


def _status_kind(s: str) -> str:
    """Classifica um status em: done | review | wip | todo | other"""
    ns = _norm(s)
    # Debug: verificar o status normalizado
    if 'concluido' in ns:
        return 'done'
    # Revisão / Análise (considera variações com ou sem 'pendente de')
    if any(k in ns for k in ['revisao','analise','pendentederevisao','pendentedeanalise']):
        return 'review'
    # Em produção - expandir as variações
    if any(k in ns for k in ['emproducao', 'emandamento', 'producao', 'progresso']):
        return 'wip'
    if any(k in ns for k in ['naoiniciado', 'naoiniciada', 'nao_iniciado']):
        return 'todo'
    return 'other'


def _parse_eps(val) -> set:
    s = str(val or '').strip()
    if not s:
        return set()
    if s.lower() == 'todos':
        return {'ALL'}
    return {int(x) for x in re.findall(r"\d+", s)}


def _split_names(resp_str: str) -> List[str]:
    """Split múltiplos responsáveis separados por / , &, etc."""
    if not resp_str or str(resp_str).strip() in ['', 'nan', 'None']:
        return []
    names = re.split(r'[/,&;]+', str(resp_str))
    return [n.strip() for n in names if n.strip()]


def create_table_png(df: pd.DataFrame, get_thumb: Optional[Callable[[str, str, int], str]] = None) -> bytes:
    """Cria uma imagem PNG da tabela com miniaturas."""
    if df.empty:
        # Criar imagem vazia se não há dados
        fig, ax = plt.subplots(figsize=(12, 2))
        ax.text(0.5, 0.5, 'Nenhum dado disponível', ha='center', va='center', fontsize=16)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150, facecolor='white')
        plt.close()
        buf.seek(0)
        return buf.getvalue()
    
    # Configurações visuais
    row_height = 90
    col_widths = [90, 250, 180, 180, 180]  # Imagem, Personagem, Status Concept, Status Rig, Responsável
    total_width = sum(col_widths)
    total_height = (len(df) + 1) * row_height  # +1 para header
    
    # Criar figura com alta qualidade
    plt.style.use('default')
    fig = plt.figure(figsize=(total_width/100, total_height/100), dpi=200)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, total_width)
    ax.set_ylim(0, total_height)
    ax.axis('off')
    
    # Cores dos status
    status_colors = {
        'wip': '#fef3c7',      # Em produção - amarelo
        'review': '#dbeafe',   # Revisão - azul
        'done': '#dcfce7',     # Concluído - verde
        'todo': '#f3f4f6',     # Não iniciado - cinza
        'other': '#fee2e2'     # Outros - vermelho
    }
    
    # Header com estilo melhorado
    headers = ['Miniatura', 'Personagem', 'Status Concept', 'Status Rig', 'Responsável']
    x_pos = 0
    for i, (header, width) in enumerate(zip(headers, col_widths)):
        # Fundo do header
        rect = patches.Rectangle((x_pos, total_height - row_height), width, row_height, 
                               linewidth=2, edgecolor='#374151', facecolor='#e5e7eb')
        ax.add_patch(rect)
        
        # Texto do header
        ax.text(x_pos + width/2, total_height - row_height/2, header, 
               ha='center', va='center', fontweight='bold', fontsize=12, color='#1f2937')
        x_pos += width
    
    # Dados das linhas
    for row_idx, (_, row) in enumerate(df.iterrows()):
        y_pos = total_height - (row_idx + 2) * row_height
        x_pos = 0
        
        # Cor de fundo alternada
        bg_color = '#ffffff' if row_idx % 2 == 0 else '#f9fafb'
        
        # Imagem (miniatura)
        img_rect = patches.Rectangle((x_pos, y_pos), col_widths[0], row_height,
                                   linewidth=1, edgecolor='#d1d5db', facecolor=bg_color)
        ax.add_patch(img_rect)
        
        if get_thumb:
            fid = str(row.get('file_id', ''))
            name = str(row.get('personagem', ''))
            thumb_uri = get_thumb(fid, name, 80)
            
            # Placeholder para miniatura
            thumb_rect = patches.Rectangle((x_pos + 5, y_pos + 5), col_widths[0] - 10, row_height - 10,
                                         linewidth=1, edgecolor='#9ca3af', facecolor='#f3f4f6', 
                                         linestyle='--', alpha=0.7)
            ax.add_patch(thumb_rect)
            
            if thumb_uri:
                # Indicador de que há miniatura
                ax.text(x_pos + col_widths[0]/2, y_pos + row_height/2, '🖼️\nMiniatura', 
                       ha='center', va='center', fontsize=10, color='#059669')
            else:
                ax.text(x_pos + col_widths[0]/2, y_pos + row_height/2, '📷\nSem imagem', 
                       ha='center', va='center', fontsize=9, color='#6b7280', alpha=0.7)
        
        x_pos += col_widths[0]
        
        # Personagem
        pers_rect = patches.Rectangle((x_pos, y_pos), col_widths[1], row_height,
                                    linewidth=1, edgecolor='#d1d5db', facecolor=bg_color)
        ax.add_patch(pers_rect)
        
        personagem = str(row.get('personagem', ''))
        # Quebrar texto se muito longo
        if len(personagem) > 25:
            personagem = personagem[:22] + '...'
        
        ax.text(x_pos + 15, y_pos + row_height/2, personagem, 
               ha='left', va='center', fontsize=11, fontweight='bold', color='#111827')
        x_pos += col_widths[1]
        
        # Status Concept
        status_concept = str(row.get('status_concept', ''))
        status_kind_concept = _status_kind(status_concept)
        color_concept = status_colors.get(status_kind_concept, '#f3f4f6')
        
        concept_rect = patches.Rectangle((x_pos, y_pos), col_widths[2], row_height,
                                       linewidth=1, edgecolor='#d1d5db', facecolor=color_concept)
        ax.add_patch(concept_rect)
        
        # Adicionar ícone de status
        status_icons = {'wip': '🟧', 'review': '🟨', 'todo': '⬜', 'done': '🟩', 'other': '🔴'}
        icon = status_icons.get(status_kind_concept, '⬜')
        
        status_text = status_concept[:15] + ('...' if len(status_concept) > 15 else '')
        ax.text(x_pos + 15, y_pos + row_height/2, f"{icon} {status_text}", 
               ha='left', va='center', fontsize=9, color='#374151')
        x_pos += col_widths[2]
        
        # Status Rig
        status_rig = str(row.get('status_rig', ''))
        status_kind_rig = _status_kind(status_rig)
        color_rig = status_colors.get(status_kind_rig, '#f3f4f6')
        
        rig_rect = patches.Rectangle((x_pos, y_pos), col_widths[3], row_height,
                                   linewidth=1, edgecolor='#d1d5db', facecolor=color_rig)
        ax.add_patch(rig_rect)
        
        icon = status_icons.get(status_kind_rig, '⬜')
        status_text = status_rig[:15] + ('...' if len(status_rig) > 15 else '')
        ax.text(x_pos + 15, y_pos + row_height/2, f"{icon} {status_text}", 
               ha='left', va='center', fontsize=9, color='#374151')
        x_pos += col_widths[3]
        
        # Responsável
        responsavel = str(row.get('responsavel', ''))
        if len(responsavel) > 20:
            responsavel = responsavel[:17] + '...'
        
        resp_rect = patches.Rectangle((x_pos, y_pos), col_widths[4], row_height,
                                    linewidth=1, edgecolor='#d1d5db', facecolor=bg_color)
        ax.add_patch(resp_rect)
        
        ax.text(x_pos + 15, y_pos + row_height/2, responsavel, 
               ha='left', va='center', fontsize=10, color='#374151')
    
    # Adicionar título e data
    fig.suptitle(f'Lista de Demandas - {pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}', 
                fontsize=16, fontweight='bold', y=0.98)
    
    # Salvar como PNG com alta qualidade
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200, facecolor='white', 
                edgecolor='none', pad_inches=0.2)
    plt.close()
    buf.seek(0)
    return buf.getvalue()


def _split_names(resp_str: str) -> List[str]:
    """Divide strings de responsáveis em nomes individuais (vírgula, barra, ponto e vírgula, 'e', '&', etc.)
    e remove duplicados preservando a ordem.
    """
    pat = re.compile(r"\s*(?:,|;|/|\||&|\+|\be\b|\band\b)\s*", re.IGNORECASE)
    parts = [p.strip() for p in pat.split(str(resp_str or '')) if str(p).strip()]
    seen = set()
    uniq: List[str] = []
    for name in parts:
        key = _norm(name)
        if key and key not in seen:
            seen.add(key)
            uniq.append(name)
    return uniq


def _dedupe_preserve(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in seq:
        key = _norm(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


_SVB_ID_RE = re.compile(r"\b(?:SVB|RIG|PER)_([A-Za-z0-9]+)\b", re.IGNORECASE)


def _extract_svb_id(*texts: str) -> str:
    """Retorna o primeiro ID normalizado 'SVB_XXXXX' encontrado nas strings fornecidas.
    Aceita variações RIG_*/PER_* e converte para SVB_*.
    """
    for t in texts:
        if not t:
            continue
        m = _SVB_ID_RE.search(str(t))
        if m:
            return f"SVB_{m.group(1).upper()}"
    return ''


def _std_svb_id(s: str) -> str:
    """Normaliza para 'SVB_XXXXX' em maiúsculas se casar o padrão (SVB|RIG|PER)."""
    m = _SVB_ID_RE.search(str(s or ''))
    return (f"SVB_{m.group(1).upper()}" if m else str(s or ''))


def build_open_tasks(df: pd.DataFrame) -> pd.DataFrame:
    """Gera linhas para tarefas abertas (WIP/Review/Todo) de Concept e Rig."""
    # Resolve nomes de colunas de acordo com o CSV atual, com fallbacks
    def pick(*cands: str) -> Optional[str]:
        for c in cands:
            if c in df.columns:
                return c
        return None

    ep_col = pick(COL_EP, 'EPS', 'Episódio', 'Episodio')
    name_col_primary = pick(COL_NAME, 'NOME', 'Nome', 'personagem', 'PERSONAGEM', 'Nome do personagem')
    name_col_alt = pick('PERSONAGEM', 'Personagem')
    id_col = pick(COL_FILE_ID, 'ID', 'Id', 'ID do Arquivo')
    rig_link_col = pick(COL_RIG_LINK, 'LINK RIG', 'Link Rig')
    sync_col = pick(COL_SYNCSKETCH, 'SYNC SKETCH', 'SyncSketch', 'Sync Sketch')
    concept_link_col = pick(COL_CONCEPT_LINK, 'LINKS CONCEPT', 'Link Concept', 'LINK CONCEPT')
    status_concept_col = pick(COL_STATUS_CONCEPT, 'STATUS CONCEPT', 'Status Concept')
    status_rig_col = pick(COL_STATUS_RIG, 'STATUS RIG', 'Status Rig')
    resp_rig_col = pick(COL_RESP_RIG, 'RESPONSÁVEL', 'Responsável', 'Responsável RIG', 'RESPONSAVEL')
    resp_concept_draw_col = pick(COL_RESP_CONCEPT, 'RESPONSÁVEL CONCEPT', 'Responsável Concept', 'Responsável (Desenho)')
    resp_concept_vect_col = pick('RESPONSÁVEL VETORIZAÇÃO', 'Responsável Vetorização', 'Responsável (Vetorização)')
    comments_col = pick(COL_COMMENTS, 'COMENTÁRIOS', 'Comentários', 'Comentarios')

    recs: List[dict] = []
    for _, r in df.iterrows():
        ep_raw = r.get(ep_col, '') if ep_col else ''
        # Nome: prioriza coluna principal, cai para alternativa
        nm_raw_primary = r.get(name_col_primary, '') if name_col_primary else ''
        nm_raw_alt = r.get(name_col_alt, '') if name_col_alt else ''
        nm = str(nm_raw_primary or nm_raw_alt or '')
        fid = str(r.get(id_col, '')) if id_col else ''
        # Concept
        status_concept_raw = str(r.get(status_concept_col, '')) if status_concept_col else ''
        sk_c = _status_kind(status_concept_raw)
        if sk_c in {'wip', 'review', 'todo'}:
            # Responsáveis de Concept: desenho + vetorização (se existirem)
            resp_c_parts: List[str] = []
            if resp_concept_draw_col:
                resp_c_parts.append(str(r.get(resp_concept_draw_col, '') or ''))
            if resp_concept_vect_col:
                resp_c_parts.append(str(r.get(resp_concept_vect_col, '') or ''))
            resp_c_merged = ' / '.join([p for p in resp_c_parts if str(p).strip()])
            recs.append({
                'episodio': ep_raw,
                'ep_first': min({e for e in _parse_eps(ep_raw) if isinstance(e, int)}) if _parse_eps(ep_raw) else 9999,
                'etapa': 'Concept',
                'nome': nm,
                'id': fid,
                'responsavel': resp_c_merged,
                'status': status_concept_raw,
                'kind': sk_c,
                'status_c': status_concept_raw,
                'status_r': str(r.get(status_rig_col, '')) if status_rig_col else '',
                'resp_c': resp_c_merged,
                'resp_r': str(r.get(resp_rig_col, '')) if resp_rig_col else '',
                'link': str(r.get(concept_link_col, '')) if concept_link_col else '',
                'sync': str(r.get(sync_col, '')) if sync_col else '',
                'comentarios': str(r.get(comments_col, '')) if comments_col else '',
            })
        # Rig
        sk_r = _status_kind(r.get(status_rig_col, '') if status_rig_col else '')
        if sk_r in {'wip', 'review', 'todo'}:
            recs.append({
                'episodio': ep_raw,
                'ep_first': min({e for e in _parse_eps(ep_raw) if isinstance(e, int)}) if _parse_eps(ep_raw) else 9999,
                'etapa': 'Rig',
                'nome': nm,
                'id': fid,
                'responsavel': str(r.get(resp_rig_col, '')) if resp_rig_col else '',
                'status': str(r.get(status_rig_col, '')) if status_rig_col else '',
                'kind': sk_r,
                'status_c': str(r.get(status_concept_col, '')) if status_concept_col else '',
                'status_r': str(r.get(status_rig_col, '')) if status_rig_col else '',
                'resp_c': str(r.get(resp_concept_draw_col, '') or '') + (
                    (" / " + str(r.get(resp_concept_vect_col, '') or '')) if resp_concept_vect_col else ''
                ),
                'resp_r': str(r.get(resp_rig_col, '')) if resp_rig_col else '',
                'link': str(r.get(rig_link_col, '')) if rig_link_col else '',
                'sync': str(r.get(sync_col, '')) if sync_col else '',
                'comentarios': str(r.get(comments_col, '')) if comments_col else '',
            })
    if not recs:
        return pd.DataFrame(columns=['episodio','ep_first','etapa','nome','id','responsavel','status','kind','status_c','status_r','resp_c','resp_r','link','sync','comentarios'])
    out = pd.DataFrame.from_records(recs)
    out.sort_values(['ep_first','etapa','nome'], inplace=True)
    return out


def render_list_tab(df: pd.DataFrame, get_thumb: Optional[Callable[[str, str, int], str]] = None):
    st.subheader('Lista — Demandas em andamento, revisão e não iniciadas')
    
    # Debug: mostrar colunas detectadas
    with st.expander("Debug: Colunas detectadas", expanded=False):
        st.write("Colunas disponíveis:", list(df.columns))
        # Resolver nomes de colunas
        def pick(*cands: str) -> Optional[str]:
            for c in cands:
                if c in df.columns:
                    return c
            return None
        status_concept_col = pick(COL_STATUS_CONCEPT, 'STATUS CONCEPT', 'Status Concept')
        resp_concept_draw_col = pick(COL_RESP_CONCEPT, 'RESPONSÁVEL CONCEPT', 'Responsável Concept')
        resp_concept_vect_col = pick('RESPONSÁVEL VETORIZAÇÃO', 'Responsável Vetorização')
        st.write(f"Status Concept col: {status_concept_col}")
        st.write(f"Resp Concept draw col: {resp_concept_draw_col}")  
        st.write(f"Resp Concept vect col: {resp_concept_vect_col}")
        if not df.empty:
            st.write("Primeiras 3 linhas relevantes:")
            cols_to_show = [c for c in [status_concept_col, resp_concept_draw_col, resp_concept_vect_col] if c]
            if cols_to_show:
                sample_df = df[cols_to_show].head(3)
                st.write(sample_df)
                # Testar normalização de status
                if status_concept_col and status_concept_col in df.columns:
                    st.write("Exemplos de status e sua classificação:")
                    for idx, row in sample_df.iterrows():
                        status_raw = str(row.get(status_concept_col, ''))
                        if status_raw.strip():
                            status_kind = _status_kind(status_raw)
                            status_norm = _norm(status_raw)
                            st.write(f"'{status_raw}' -> norm: '{status_norm}' -> kind: '{status_kind}'")
        
        # Debug de thumbnails se houver get_thumb
        if get_thumb is not None:
            st.write("**Debug de Thumbnails:**")
            test_chars = ['MURIEL', 'CURUCA', 'PEPE PESCADOR', 'CARIBÉ']
            test_ids = ['SVB_RIG_MURIEL', 'SVB_RIG_CURUCA', 'SVB_RIG_PEPE_PESCADOR', 'SVB_RIG_CARIBE']
            
            for char, test_id in zip(test_chars, test_ids):
                thumb_result = get_thumb(test_id, char, 32)
                status = "✅ Encontrada" if thumb_result else "❌ Não encontrada"
                st.write(f"{char} ({test_id}): {status}")
    
    # Estilos visuais
    st.markdown(textwrap.dedent("""
<style>
.svb-card { padding:10px 12px; border:1px solid #2a2d33; border-radius:10px; margin:8px 0; background:transparent; }
.svb-row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.svb-title { font-weight:600; }
.svb-badge { padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }
.svb-badge.concept { background:#1e3a8a; color:#dbeafe; }
.svb-badge.rig { background:#5b21b6; color:#ede9fe; }
.svb-badge.wip { background:#9a3412; color:#ffedd5; }
.svb-badge.review { background:#854d0e; color:#fef3c7; }
.svb-badge.todo { background:#374151; color:#e5e7eb; }
.svb-chip { background:#f3f4f6; border:1px solid #e5e7eb; border-radius:999px; padding:2px 8px; font-size:12px; display:inline-block; margin:0 4px 4px 0; }
.svb-meta { opacity:0.85; font-size:12px; }
.svb-thumb { width:48px; height:48px; object-fit:cover; border-radius:8px; border:1px solid #e5e7eb; }
</style>
"""), unsafe_allow_html=True)
    tasks = build_open_tasks(df)
    if tasks.empty:
        st.info('Nenhuma demanda aberta encontrada.')
        return

    # Garante colunas esperadas para evitar KeyError em filtros
    expected_cols = ['episodio','ep_first','etapa','nome','id','responsavel','status','kind','status_c','status_r','resp_c','resp_r','link','sync','comentarios']
    for c in expected_cols:
        if c not in tasks.columns:
            tasks[c] = pd.Series(dtype=object)

    # Filtros
    # Episódios
    all_eps = sorted({e for v in df.get(COL_EP, []).tolist() for e in _parse_eps(v) if isinstance(e, int)})
    sel_eps = st.multiselect('Episódios', options=all_eps, default=all_eps, key='ls_eps')
    sel_eps_set = set(sel_eps)
    # Etapas e responsáveis
    etapas = st.multiselect('Etapas', options=['Concept','Rig'], default=['Concept','Rig'], key='ls_etapas')
    # Extrai responsáveis individuais (suporta múltiplos nomes por célula)
    _all_resp_cells = [x for x in tasks['responsavel'].dropna().astype(str).tolist() if str(x).strip()]
    resps = sorted({n for cell in _all_resp_cells for n in _split_names(cell) if str(n).strip()})
    sel_resps = st.multiselect('Responsáveis', options=resps, key='ls_resps')
    q = st.text_input('Buscar nome ou ID', key='ls_q')
    # Estágios de produção (filtro)
    stage_options = ['Em produção', 'Pendente de revisão', 'Não iniciado']
    stage_to_kind = {
        'Em produção': 'wip',
        'Pendente de revisão': 'review',
        'Não iniciado': 'todo',
    }
    # Visualização padrão: Em produção + Pendente de revisão (análise) + Não iniciado
    sel_stages = st.multiselect('Estágios', options=stage_options, default=stage_options, key='ls_stages')
    sel_kinds = {stage_to_kind[s] for s in sel_stages}

    fil = tasks.copy()
    if sel_kinds:
        fil = fil[fil['kind'].isin(sel_kinds)]
    # Aplicar filtros adicionais antes da agregação
    if sel_eps:
        fil = fil[fil['episodio'].apply(lambda v: ('ALL' in _parse_eps(v)) or (len(_parse_eps(v) & sel_eps_set) > 0))]
    if etapas and 'etapa' in fil.columns:
        fil = fil[fil['etapa'].isin(etapas)]
    if sel_resps:
        _sel_norm = {_norm(x) for x in sel_resps}
        fil = fil[fil['responsavel'].apply(lambda v: any(_norm(n) in _sel_norm for n in _split_names(v)))]
    if q:
        qn = str(q).strip().lower()
        fil = fil[(fil['nome'].astype(str).str.lower().str.contains(qn)) | (fil['id'].astype(str).str.lower().str.contains(qn))]
    # Dedupe por personagem (ID) e etapa; agrega episódios e escolhe o status mais "aberto"
    def _safe_eps_set(v):
        try:
            return _parse_eps(v)
        except Exception:
            return set()

    if 'episodio' not in fil.columns:
        fil['episodio'] = pd.Series(dtype=object)
    fil['__eps_set__'] = fil['episodio'].apply(_safe_eps_set)
    rank_map = {'wip':3, 'review':2, 'todo':1}
    fil['__rank__'] = fil['kind'].map(rank_map).fillna(0)

    # Agrega por (id, nome) — um cartão por personagem com ambos os status
    groups = []
    for (pid, nome), g in fil.groupby(['id','nome'], dropna=False):
        gs = g.sort_values('__rank__', ascending=False)
        # Melhores status por etapa
        status_c = next((s for s in gs['status_c'].tolist() if str(s).strip()), '')
        status_r = next((s for s in gs['status_r'].tolist() if str(s).strip()), '')
        kind_c = _status_kind(status_c)
        kind_r = _status_kind(status_r)
        # Responsáveis (agregados e únicos)
        _resp_c_all: List[str] = []
        for s in gs['resp_c'].tolist():
            _resp_c_all.extend(_split_names(s))
        resp_c = ', '.join(_dedupe_preserve(_resp_c_all))

        _resp_r_all: List[str] = []
        for s in gs['resp_r'].tolist():
            _resp_r_all.extend(_split_names(s))
        resp_r = ', '.join(_dedupe_preserve(_resp_r_all))
        # Comentários (qualquer)
        comments = next((c for c in gs['comentarios'].tolist() if str(c).strip()), '')
        # ID melhorado: tenta extrair SVB_ a partir de id/link/sync/comentários/nome
        links = [s for s in gs.get('link', pd.Series([], dtype=object)).astype(str).tolist() if str(s).strip()]
        syncs = [s for s in gs.get('sync', pd.Series([], dtype=object)).astype(str).tolist() if str(s).strip()]
        
        # Melhor extração de ID: tenta múltiplas fontes
        candidate_ids = []
        
        # 1. ID original da linha
        if str(pid).strip():
            candidate_ids.append(str(pid))
        
        # 2. IDs extraídos de links e syncs
        for text in links + syncs + [comments]:
            extracted = _extract_svb_id(text)
            if extracted:
                candidate_ids.append(extracted)
        
        # 3. Construir ID a partir do nome
        if nome:
            nome_clean = re.sub(r'[^a-zA-Z0-9_]', '_', nome.upper().strip())
            nome_clean = re.sub(r'_+', '_', nome_clean).strip('_')
            if nome_clean:
                candidate_ids.extend([
                    f"SVB_RIG_{nome_clean}",
                    f"SVB_PER_{nome_clean}",
                    f"SVB_{nome_clean}"
                ])
        
        # 4. Normalizar todos os candidatos
        normalized_candidates = []
        for cid in candidate_ids:
            norm_id = _std_svb_id(cid)
            if norm_id and norm_id not in normalized_candidates:
                normalized_candidates.append(norm_id)
        
        # Usar o primeiro candidato válido ou o ID original
        best_id = normalized_candidates[0] if normalized_candidates else str(pid)
        
        link_agg = next((x for x in links if x), '')
        sync_agg = next((x for x in syncs if x), '')

        # Kind agregado para ordenação/filtragem
        agg_rank = max(rank_map.get(kind_c, 0), rank_map.get(kind_r, 0))
        agg_kind = next((k for k,v in rank_map.items() if v == agg_rank), 'other')
        groups.append({
            'id': best_id,
            'nome': nome,
            'status_c': status_c,
            'status_r': status_r,
            'kind_c': kind_c,
            'kind_r': kind_r,
            'resp_c': resp_c,
            'resp_r': resp_r,
            'comentarios': comments,
            'link': link_agg,
            'sync': sync_agg,
            'kind': agg_kind,
        })
    agg = pd.DataFrame(groups) if groups else fil.head(0).copy()
    if not agg.empty:
        agg.sort_values(['nome'], inplace=True)

    # Resumo (dedupado)
    st.metric('Total', len(agg))
    # Lista simples em formato de tabela
    st.divider()
    if agg.empty:
        st.info('Nenhum item com os filtros atuais.')
        return

    # Botões de ação em colunas
    col1, col2 = st.columns(2)
    
    with col1:
        # Botão para atualizar miniaturas (força bust de cache variando levemente o tamanho)
        if st.button('🔄 Atualizar miniaturas', key='ls_refresh_thumbs'):
            st.session_state['ls_thumb_nonce'] = st.session_state.get('ls_thumb_nonce', 0) + 1
    
    with col2:
        # Botão para exportar como PNG
        if st.button('📷 Exportar como PNG', key='ls_export_png'):
            with st.spinner('Gerando imagem PNG...'):
                try:
                    # Preparar dados para PNG
                    display_df = agg.copy()
                    display_df = display_df.rename(columns={
                        'nome': 'personagem',
                        'id': 'file_id',
                        'status_c': 'status_concept',
                        'status_r': 'status_rig'
                    })
                    
                    # Gerar PNG
                    png_bytes = create_table_png(display_df, get_thumb)
                    
                    # Criar download
                    st.download_button(
                        label="⬇️ Baixar PNG",
                        data=png_bytes,
                        file_name=f"lista_demandas_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png",
                        mime="image/png",
                        key='download_png'
                    )
                    st.success("PNG gerado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao gerar PNG: {str(e)}")

    def _status_badge_text(s: str) -> str:
        k = _status_kind(s)
        icon = { 'wip':'🟧', 'review':'🟨', 'todo':'⬜', 'done':'🟩' }.get(k, '⬜')
        return f"{icon} {s or '—'}"

    thumbs: List[str] = []
    nonce = int(st.session_state.get('ls_thumb_nonce', 0))
    thumb_size = 64 + (nonce % 3)
    if get_thumb is not None:
        for _, r in agg.iterrows():
            try:
                # Estratégia aprimorada de candidatos para thumbnail
                candidates: List[str] = []
                nome_char = str(r.get('nome', ''))
                
                # 1. ID agregado (primeiro candidato)
                main_id = str(r.get('id', ''))
                if main_id:
                    candidates.append(main_id)
                
                # 2. IDs extraídos de outras fontes
                for src in [r.get('link',''), r.get('sync',''), r.get('comentarios','')]:
                    extracted = _extract_svb_id(str(src))
                    if extracted:
                        candidates.append(extracted)
                
                # 3. Construir IDs a partir do nome do personagem
                if nome_char:
                    nome_variants = []
                    
                    # Nome original limpo
                    nome_norm = re.sub(r'[^a-zA-Z0-9_]', '_', nome_char.upper().strip())
                    nome_norm = re.sub(r'_+', '_', nome_norm).strip('_')
                    if nome_norm:
                        nome_variants.append(nome_norm)
                    
                    # Variações para nomes compostos (ex: "TIA REBIMBOCA DE MOCHILA" -> "TIA_REBIMBOCA")
                    # Remove palavras conectoras comuns
                    nome_sem_conectores = re.sub(r'\b(DE|DA|DO|E|COM|PARA|EM|NA|NO)\b', '', nome_char.upper())
                    nome_sem_conectores = re.sub(r'[^a-zA-Z0-9_]', '_', nome_sem_conectores.strip())
                    nome_sem_conectores = re.sub(r'_+', '_', nome_sem_conectores).strip('_')
                    if nome_sem_conectores and nome_sem_conectores != nome_norm:
                        nome_variants.append(nome_sem_conectores)
                    
                    # Primeira palavra + segunda palavra (ex: "TIA_REBIMBOCA")
                    palavras = [p for p in re.split(r'[_\s]+', nome_char.upper()) if len(p) >= 3]
                    if len(palavras) >= 2:
                        nome_curto = f"{palavras[0]}_{palavras[1]}"
                        nome_variants.append(nome_curto)
                    
                    # Adicionar todas as variações
                    for variant in nome_variants:
                        if variant:
                            candidates.extend([
                                f"SVB_RIG_{variant}",
                                f"SVB_PER_{variant}",
                                f"SVB_{variant}",
                                variant  # Nome puro para fallback
                            ])
                    
                    # Tentar palavras individuais como fallback
                    for palavra in palavras:
                        if len(palavra) >= 4:  # Palavras maiores
                            candidates.extend([
                                f"SVB_RIG_{palavra}",
                                f"SVB_PER_{palavra}",
                                f"SVB_{palavra}"
                            ])
                
                # 4. Normalizar e dedupe preservando ordem
                seen = set()
                unique_candidates: List[str] = []
                for c in candidates:
                    normalized = _std_svb_id(c) if c else c
                    if normalized and normalized.upper() not in seen:
                        seen.add(normalized.upper())
                        unique_candidates.append(normalized)
                
                # 5. Tentar cada candidato até encontrar uma imagem
                img_data = ''
                for cid in unique_candidates:
                    img_data = get_thumb(cid, nome_char, thumb_size) or ''
                    if img_data:
                        break
                
                thumbs.append(img_data)
            except Exception as e:
                # Debug: log do erro se necessário
                thumbs.append('')
    else:
        thumbs = ['' for _ in range(len(agg))]

    tdf = pd.DataFrame({
        'Imagem': thumbs,
        'Personagem': agg['nome'].astype(str).tolist(),
        'Status Rig': [
            f"{_status_badge_text(s)} — {r if str(r).strip() else '—'}"
            for s, r in zip(agg['status_r'].tolist(), agg['resp_r'].astype(str).tolist())
        ],
        'Status Concept': [
            f"{_status_badge_text(s)} — {r if str(r).strip() else '—'}"
            for s, r in zip(agg['status_c'].tolist(), agg['resp_c'].astype(str).tolist())
        ],
    })

    # Renderização da tabela com imagens
    try:
        # Altura dinâmica para evitar scroll interno
        _row_h = 42
        _height = _row_h * (len(tdf) + 1) + 12
        st.dataframe(
            tdf,
            use_container_width=True,
            hide_index=True,
            height=_height,
            column_config={
                'Imagem': st.column_config.ImageColumn("Imagem", width="small"),
                'Personagem': st.column_config.Column("Personagem", width="medium"),
                'Status Rig': st.column_config.Column("Status Rig", width="medium"),
                'Status Concept': st.column_config.Column("Status Concept", width="medium"),
            },
        )
    except Exception:
        # Fallback simples
        st.table(tdf)
    
    # Lista de demandas por pessoa
    st.divider()
    st.subheader('📋 Demandas por Pessoa')
    
    # Criar lista de todas as demandas individuais por responsável (sem duplicatas de personagem)
    person_tasks = []
    for _, r in fil.iterrows():
        # Extrair responsáveis de cada linha
        resp_names = _split_names(str(r.get('responsavel', '')))
        for resp in resp_names:
            if str(resp).strip():
                person_tasks.append({
                    'responsavel': resp.strip(),
                    'personagem': str(r.get('nome', '')),
                    'etapa': str(r.get('etapa', '')),
                    'status': str(r.get('status', '')),
                    'kind': str(r.get('kind', '')),
                    'episodio': str(r.get('episodio', '')),
                })
    
    if person_tasks:
        # Agrupar por responsável e personagem para remover duplicatas
        person_df = pd.DataFrame(person_tasks)
        
        # Agregar por (responsavel, personagem) - combinar etapas
        agg_person_tasks = []
        for (resp, char), group in person_df.groupby(['responsavel', 'personagem']):
            etapas = sorted(group['etapa'].unique())
            etapa_combined = ' + '.join(etapas)
            
            # Pegar o status mais prioritário (wip > review > todo)
            kinds = group['kind'].tolist()
            priority_order = {'wip': 3, 'review': 2, 'todo': 1, 'other': 0}
            best_kind = max(kinds, key=lambda k: priority_order.get(k, 0))
            best_status = group[group['kind'] == best_kind]['status'].iloc[0]
            
            # Pegar episódio (assumindo que é o mesmo para o personagem)
            episodio = group['episodio'].iloc[0]
            
            agg_person_tasks.append({
                'responsavel': resp,
                'personagem': char,
                'etapa': etapa_combined,
                'status': best_status,
                'kind': best_kind,
                'episodio': episodio,
            })
        
        # Criar interface com tabs por pessoa
        person_df_agg = pd.DataFrame(agg_person_tasks)
        responsaveis_unicos = sorted(person_df_agg['responsavel'].unique())
        
        if len(responsaveis_unicos) > 0:
            # Criar selectbox para escolher responsável
            selected_person = st.selectbox(
                'Selecionar responsável:',
                options=['Todos'] + responsaveis_unicos,
                key='person_selector'
            )
            
            if selected_person == 'Todos':
                # Mostrar resumo por pessoa
                st.write("**Resumo geral:**")
                summary_data = []
                for resp in responsaveis_unicos:
                    resp_tasks = person_df_agg[person_df_agg['responsavel'] == resp]
                    total = len(resp_tasks)
                    wip = len(resp_tasks[resp_tasks['kind'] == 'wip'])
                    review = len(resp_tasks[resp_tasks['kind'] == 'review'])
                    todo = len(resp_tasks[resp_tasks['kind'] == 'todo'])
                    
                    summary_data.append({
                        'Responsável': resp,
                        'Total': total,
                        '🟧 Em Produção': wip,
                        '🟨 Revisão': review,
                        '⬜ Não Iniciado': todo
                    })
                
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                
            else:
                # Mostrar tarefas da pessoa selecionada
                person_tasks_filtered = person_df_agg[person_df_agg['responsavel'] == selected_person]
                
                st.write(f"**Demandas de {selected_person}:** {len(person_tasks_filtered)} personagens")
                
                # Agrupar por status
                for kind, kind_name, emoji in [('wip', 'Em Produção', '🟧'), ('review', 'Pendente de Revisão', '🟨'), ('todo', 'Não Iniciado', '⬜')]:
                    kind_tasks = person_tasks_filtered[person_tasks_filtered['kind'] == kind]
                    if not kind_tasks.empty:
                        st.write(f"**{emoji} {kind_name}** ({len(kind_tasks)} personagens):")
                        
                        task_display = []
                        for _, task in kind_tasks.iterrows():
                            task_display.append({
                                'Personagem': task['personagem'],
                                'Etapa(s)': task['etapa'],
                                'Episódio': task['episodio'],
                                'Status': task['status']
                            })
                        
                        task_df = pd.DataFrame(task_display)
                        st.dataframe(
                            task_df,
                            use_container_width=True,
                            hide_index=True,
                            height=min(300, len(task_df) * 35 + 50)
                        )
    else:
        st.info('Nenhuma demanda encontrada para os filtros atuais.')
    
    # (antiga listagem por episódio removida em favor dos cartões dedupados)
