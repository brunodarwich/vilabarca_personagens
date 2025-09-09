"""
Aplicativo Streamlit — Dashboard de Produção por Episódio

Descrição rápida
- Lê um CSV com os personagens e seus status (Concept/Rig), além de responsáveis, urgência e links.
- Indexa imagens na pasta `personagens/` para exibir miniaturas por personagem.
- Exibe filtros na barra lateral e agrupa os resultados por episódio, em cards ou tabela.

Como executar (local)
- Crie/ative um ambiente Python 3.12.
- Instale as dependências (requirements.txt).
- Rode: `streamlit run app.py`.

Estrutura de alto nível
- Helpers: funções utilitárias de normalização, parsing e resolução de imagens.
- Data loading: leitura e normalização do CSV, cacheada via Streamlit.
- UI: CSS e layout, filtros, agrupamento por episódio e renderização (cards/tabela).
"""

import os
import re
import unicodedata
import base64
import mimetypes
import io
from urllib.parse import urlencode
from pathlib import Path


import pandas as pd
import streamlit as st
from unidecode import unidecode
try:
    # Opcional: auto-refresh sem JS (pip install streamlit-autorefresh)
    from streamlit_autorefresh import st_autorefresh  # type: ignore
except Exception:
    st_autorefresh = None
from stats import (
    overall_stats,
    episode_completion,
    status_breakdown,
    urgency_breakdown,
    responsavel_breakdown,
)
from timeline import render_timeline_tab
from list_tab import render_list_tab

# Paths
# BASE_DIR: raiz do projeto; CSV_PATH: caminho do CSV; IMG_DIR: pasta com imagens dos personagens
BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "SVB_INDEX.xlsx - RIG.csv"
IMG_DIR = BASE_DIR / "personagens"

# CSV column names (padrão interno). Mantemos nomes antigos para compatibilidade;
# ao ler o CSV, renomeamos colunas novas/antigas para estes identificadores.
COL_EP = "Episódio"
COL_NAME = "Nome do perosnagem"
COL_FILE_ID = "ID do Arquivo"
COL_RIG_LINK = "Link para baixar o modelo Rigado"
COL_SYNCSKETCH = "Link do SyncSketch"
COL_CONCEPT_LINK = "Link para baixar o modelo Ceoncept vetorizado"
COL_URG_CONCEPT = "URGÊNCIA"
COL_STATUS_CONCEPT = "Status do Concept"
COL_RESP_CONCEPT = "Responsável"
COL_URG_RIG = "URGÊNCIA.1"
COL_STATUS_RIG = "Status do Rig"
COL_RESP_RIG = "Respondável"
COL_COMMENTS = "COMENTÁRIOS"
COL_DATE_CONCEPT = "Entrega Concept"
COL_DATE_RIG = "Entrega Rig"

# ----------------- Helpers -----------------
# Funções auxiliares para lidar com textos, chaves, episódios e imagens.

def coalesce(*vals):
    """Retorna o primeiro valor não vazio (strings com conteúdo ou não-strings).

    Exemplo: coalesce(None, '  ', 'A', 'B') -> 'A'
    """
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str):
            v2 = v.strip()
            if v2:
                return v2
        else:
            return v
    return ""


def _normalize_text(s: str) -> str:
    """Normaliza texto: minúsculas, remove acentos/diacríticos e espaços extremos.

    Útil para comparar valores (status, urgência, nomes) de forma robusta.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.strip().lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def norm_key(s: str) -> str:
    """Cria uma chave "segura" (apenas a-z0-9) a partir de um texto normalizado."""
    s = _normalize_text(s)
    return re.sub(r"[^a-z0-9]+", "", s)


def is_concluido(s: str) -> bool:
    """Retorna True se o status normalizado for 'concluido'."""
    return _normalize_text(s) == "concluido"


def normalize_responsavel(s: str) -> str:
    """Normaliza alias de responsáveis (ex.: 'Oto' -> 'OTONIEL')."""
    raw = coalesce(s)
    mapping = {"oto": "OTONIEL"}
    return mapping.get(_normalize_text(raw), raw)


def parse_episode_field(ep_field: str):
    """Converte o campo de Episódio do CSV em uma lista de inteiros.

    - Retorna ['Todos'] se o texto for 'todos'.
    - Extrai todos os números independente de vírgulas, 'e', etc. (ex.: '101, 102 e 113').
    - Ignora tokens não numéricos.
    """
    if not ep_field:
        return []
    ep_field = str(ep_field).strip()
    if not ep_field:
        return []
    if ep_field.lower() == "todos":
        return ["Todos"]
    # Extrai todos os números
    return [int(n) for n in re.findall(r"\d+", ep_field)]


def detect_all_numeric_episodes(df: pd.DataFrame):
    """Extrai e ordena todos os episódios numéricos presentes no DataFrame."""
    eps = set()
    for raw in df.get(COL_EP, []).tolist():
        for p in parse_episode_field(raw):
            if isinstance(p, int):
                eps.add(p)
    return sorted(eps)


def index_images(img_dir: Path):
    """Cria um índice {chave_normalizada: caminho_imagem} a partir dos arquivos da pasta.

    - Aceita extensões comuns (png, jpg, jpeg, webp, gif).
    - Usa o nome do arquivo (sem extensão) como base para a chave.
    - Apenas arquivos cujo nome comece com 'SVB_' são indexados (regra de negócio solicitada).
    """
    idx = {}
    if not img_dir.is_dir():
        return idx
    for p in img_dir.iterdir():
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        # Exigir prefixo SVB_ no nome do arquivo
        if not p.stem.upper().startswith("SVB_"):
            continue
        key = norm_key(p.stem)
        if key and key not in idx:
            idx[key] = str(p)
    return idx


def _strip_prefixes(s: str) -> str:
    """Remove prefixos comuns de IDs (ex.: 'svb_rig_', 'rig_', 'per_')."""
    s2 = _normalize_text(s)
    for pref in ("svb_rig_", "svb_per_", "svb_", "rig_", "per_"):
        if s2.startswith(pref):
            return s2[len(pref):]
    return s2


def find_image_for(img_idx: dict, file_id: str, name: str) -> str:
    """Localiza imagem por ID e nome com múltiplas estratégias de matching.

    Estratégias em ordem de prioridade:
    1. Match exato do ID
    2. Variações RIG/PER do ID 
    3. Match por nome normalizado
    4. Match parcial por partes do nome
    5. Match por ID sem prefixos (base)
    """
    fid = (file_id or "").strip()
    name = (name or "").strip()
    
    def try_match(candidate_id: str) -> str:
        key = norm_key(candidate_id)
        return img_idx.get(key, "")
    
    # Estratégia 1: Match exato do ID
    if fid and fid.upper().startswith("SVB_"):
        result = try_match(fid)
        if result:
            return result
        
        # Estratégia 2: Variações RIG/PER do ID
        up = fid.upper()
        if up.startswith("SVB_RIG_"):
            # Tenta SVB_PER_
            result = try_match("SVB_PER_" + fid[8:])
            if result:
                return result
            # Tenta base SVB_
            base = fid[8:]  # Remove SVB_RIG_
            result = try_match("SVB_" + base)
            if result:
                return result
        elif up.startswith("SVB_PER_"):
            # Tenta SVB_RIG_
            result = try_match("SVB_RIG_" + fid[8:])
            if result:
                return result
            # Tenta base SVB_
            base = fid[8:]  # Remove SVB_PER_
            result = try_match("SVB_" + base)
            if result:
                return result
        elif up.startswith("SVB_"):
            # Para IDs SVB_ simples, tenta adicionar RIG/PER
            base = fid[4:]  # Remove SVB_
            for prefix in ["SVB_RIG_", "SVB_PER_"]:
                result = try_match(prefix + base)
                if result:
                    return result
    
    # Estratégia 3: Match por nome normalizado
    if name:
        name_norm = norm_key(name)
        
        # Criar variações do nome para matching
        name_variants = [name_norm]
        
        # Remove conectores comuns (de, da, do, e, com, etc.)
        name_clean = re.sub(r'\b(de|da|do|e|com|para|em|na|no)\b', '', name.lower())
        name_clean_norm = norm_key(name_clean)
        if name_clean_norm != name_norm:
            name_variants.append(name_clean_norm)
        
        # Casos especiais para nomes compostos específicos
        special_cases = {
            'tia_rebimboca_de_mochila': ['tia_rebimboca', 'rebimboca', 'rebi_mochila'],
            'tia_rebimboca': ['rebimboca', 'rebi'],
            'pepe_pescador': ['pepe_pescador', 'pepe'],
            'seu_tonho': ['seutonho'],
            'xico_apicultor': ['xico_apicultor', 'xico'],
            'xico_rio': ['xico_rio', 'xico']
        }
        
        if name_clean_norm in special_cases:
            name_variants.extend(special_cases[name_clean_norm])
        
        # Primeira + segunda palavra
        words = [w for w in re.split(r'[_\s]+', name_norm) if len(w) >= 3]
        if len(words) >= 2:
            name_variants.append(f"{words[0]}_{words[1]}")
        
        # Adiciona apenas a primeira palavra significativa
        if words:
            name_variants.append(words[0])
        
        # Match direto com variações
        for variant in name_variants:
            for idx_key, path in img_idx.items():
                # Extrai a parte útil do nome do arquivo (remove SVB_RIG_, SVB_PER_, etc.)
                file_name_parts = idx_key.replace('svb_rig_', '').replace('svb_per_', '').replace('svb_', '')
                
                # Match exato
                if variant == file_name_parts:
                    return path
        
        # Estratégia 4: Match parcial por partes do nome
        for variant in name_variants:
            for idx_key, path in img_idx.items():
                file_name_parts = idx_key.replace('svb_rig_', '').replace('svb_per_', '').replace('svb_', '')
                
                # Match se o nome contém ou está contido no arquivo
                if (variant in file_name_parts and len(variant) >= 4) or \
                   (file_name_parts in variant and len(file_name_parts) >= 4):
                    return path
        
        # Estratégia 5: Match usando partes do nome divididas
        for part in words:
            if len(part) >= 4:  # Palavras maiores têm prioridade
                for idx_key, path in img_idx.items():
                    if part in idx_key:
                        return path
    
    return ""


# ----------------- Data loading -----------------

@st.cache_data(show_spinner=False)
def load_dataframe(csv_path: Path) -> pd.DataFrame:
    """Lê o CSV com encoding utf-8-sig e normaliza colunas importantes.

    Também aplica um mapeamento simples de aliases de responsáveis.
    O resultado é cacheado para performance enquanto os dados não mudarem.
    """
    # Leitura robusta: alguns CSVs têm uma linha de banner antes do cabeçalho real
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    try:
        normcols = {norm_key(c) for c in df.columns}
        if ("eps" not in normcols and "episodio" not in normcols) or any(
            "sensacional" in norm_key(c) for c in df.columns
        ):
            df2 = pd.read_csv(csv_path, encoding="utf-8-sig", header=1)
            norm2 = {norm_key(c) for c in df2.columns}
            if ("eps" in norm2 or "episodio" in norm2):
                df = df2
    except Exception:
        pass

    # Renomeia colunas de acordo com o novo layout (e mantém compatibilidade com o antigo)
    def _rename_headers_for_schema(df_in: pd.DataFrame) -> pd.DataFrame:
        ren = {}
        for col in df_in.columns:
            raw = str(col)
            has_suffix = raw.endswith(".1")
            base = raw[:-2] if has_suffix else raw
            n = _normalize_text(base)
            nk = norm_key(base)
            # Mapeamentos por base normalizada
            if nk in {"episodio", "episodios", "eps"}:
                ren[raw] = COL_EP
            elif nk in {"nome", "nomedoperosnagem", "nomepersonagem", "nomedopersonagem"}:
                ren[raw] = COL_NAME
            elif nk in {"id", "iddoarquivo", "iddoarquivo"}:
                ren[raw] = COL_FILE_ID
            elif nk in {"linkrig", "linkdorig", "linkparabaixaromodelorigado"}:
                ren[raw] = COL_RIG_LINK
            elif nk in {"syncsketch", "syncsketch"}:
                ren[raw] = COL_SYNCSKETCH
            elif nk in {"linksconcept", "linkconcept", "linkdoconcept", "linkparabaixaromodeloceonceptvetorizado"}:
                ren[raw] = COL_CONCEPT_LINK
            elif nk in {"statusrig"}:
                ren[raw] = COL_STATUS_RIG
            elif nk in {"statusconcept", "vetorizacao"}:
                ren[raw] = COL_STATUS_CONCEPT
            elif nk in {"modelsheet", "modelsheet"}:
                # Sem uso direto, manter coluna caso precise no futuro
                ren[raw] = raw
            elif nk in {"responsavel", "respondavel"}:
                # Primeiro RESPONSÁVEL => Rig; Segundo ('.1') => Concept
                ren[raw] = COL_RESP_CONCEPT if has_suffix else COL_RESP_RIG
            elif nk in {"entrega"}:
                # ENTREGA agora é data de entrega (uma para Rig, outra para Concept)
                ren[raw] = COL_DATE_CONCEPT if has_suffix else COL_DATE_RIG
            elif nk in {"comentarios", "comentario"}:
                ren[raw] = COL_COMMENTS
            # Caso já sejam nomes antigos/certos, não renomeamos
        if ren:
            df_out = df_in.rename(columns=ren)
        else:
            df_out = df_in
        return df_out

    df = _rename_headers_for_schema(df)
    # Colapsar colunas duplicadas (ex.: 'Status do Concept' e 'VETORIZAÇÃO' mapeadas para o mesmo nome)
    try:
        dup_names = pd.Index(df.columns)[pd.Index(df.columns).duplicated()].unique().tolist()
        for name in dup_names:
            subset = df.loc[:, df.columns == name]
            # Combina por primeira célula não vazia (prioriza strings não vazias; senão, não-nulos)
            def _first_nonempty(row):
                for v in row:
                    if isinstance(v, str):
                        if v.strip():
                            return v
                    else:
                        if pd.notna(v):
                            return v
                return ''
            combined = subset.apply(_first_nonempty, axis=1)
            # Remove todas as ocorrências e recoloca apenas uma
            df = df.loc[:, ~(df.columns == name)]
            df[name] = combined
    except Exception:
        pass
    # Normalize string columns, apply responsible mapping
    # Garantir coluna de nome e coalescer com PERSONAGEM quando existir
    if COL_NAME in df.columns:
        df[COL_NAME] = df[COL_NAME].fillna('').astype(str)
    else:
        df[COL_NAME] = ''
    if 'PERSONAGEM' in df.columns:
        mask_empty = df[COL_NAME].astype(str).str.strip().eq('')
        df.loc[mask_empty, COL_NAME] = df.loc[mask_empty, 'PERSONAGEM'].fillna('').astype(str)
    df[COL_FILE_ID] = df.get(COL_FILE_ID, '').fillna('').astype(str)
    for c in [COL_STATUS_CONCEPT, COL_STATUS_RIG, COL_URG_CONCEPT, COL_URG_RIG, COL_RESP_CONCEPT, COL_RESP_RIG, COL_COMMENTS, COL_DATE_CONCEPT, COL_DATE_RIG]:
        if c in df.columns:
            df[c] = df[c].fillna('')
    # Map responsavel alias
    if COL_RESP_CONCEPT in df.columns:
        df[COL_RESP_CONCEPT] = df[COL_RESP_CONCEPT].map(normalize_responsavel)
    if COL_RESP_RIG in df.columns:
        df[COL_RESP_RIG] = df[COL_RESP_RIG].map(normalize_responsavel)
    return df


def _dir_signature(img_dir: Path) -> str:
    """Gera uma assinatura do diretório (nome + mtime + size) para invalidar cache quando mudar."""
    try:
        entries = []
        if img_dir.is_dir():
            for p in img_dir.iterdir():
                if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
                    stt = p.stat()
                    entries.append(f"{p.name}:{stt.st_mtime_ns}:{stt.st_size}")
        entries.sort()
        return str(hash('|'.join(entries)))
    except Exception:
        return '0'


@st.cache_data(show_spinner=False)
def load_images_index(sig: str) -> dict:
    """Indexa as imagens da pasta `personagens/`. O parâmetro sig força reindex quando a pasta mudar."""
    # sig é usado apenas para invalidar o cache quando o diretório muda
    _ = sig
    return index_images(IMG_DIR)


@st.cache_data(show_spinner=False)
def image_to_data_uri(path: str, mtime_ns: int) -> str:
    """Converte um arquivo de imagem local em data URI (base64) para uso no src do <img>.

    Isso evita bloqueios de navegador ao tentar carregar caminhos locais (C:/...).
    """
    try:
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            # fallback razoável
            mime = 'image/png'
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f"data:{mime};base64,{data}"
    except Exception:
        return ''


@st.cache_data(show_spinner=False)
def build_base_exp(df: pd.DataFrame, all_eps_tuple: tuple[int, ...]) -> pd.DataFrame:
    """Pré-processa a base uma vez e cacheia:
    - Converte episódio em lista e replica 'Todos' para todos os numéricos.
    - Explode em linhas por episódio.
    - Cria colunas normalizadas para busca e flags de conclusão vetorizadas.
    """
    base = df.copy()
    base['__EP_LIST__'] = base[COL_EP].map(parse_episode_field)
    all_eps = list(all_eps_tuple)
    if all_eps:
        def _expand(lst):
            if isinstance(lst, list) and any((isinstance(x, str) and str(x).lower() == 'todos') for x in lst):
                return all_eps
            return lst
        base['__EP_LIST__'] = base['__EP_LIST__'].apply(_expand)
    base = base.explode('__EP_LIST__')
    base = base[base['__EP_LIST__'].apply(lambda x: isinstance(x, int))]
    # Normalizações para busca
    base['__name_norm__'] = base[COL_NAME].astype(str).map(lambda s: ''.join(ch for ch in unidecode(s.lower()) if ch.isalnum()))
    base['__id_norm__'] = base[COL_FILE_ID].astype(str).map(lambda s: ''.join(ch for ch in unidecode(s.lower()) if ch.isalnum()))
    # Garantir colunas esperadas para evitar KeyError
    for need in [COL_STATUS_CONCEPT, COL_STATUS_RIG, COL_URG_CONCEPT, COL_URG_RIG, COL_RESP_CONCEPT, COL_RESP_RIG]:
        if need not in base.columns:
            base[need] = ''
    # Flags concluído (vetorizadas)
    base['__ok_c__'] = base[COL_STATUS_CONCEPT].map(is_concluido)
    base['__ok_r__'] = base[COL_STATUS_RIG].map(is_concluido)
    base['__ok_both__'] = base['__ok_c__'] & base['__ok_r__']
    return base


@st.cache_data(show_spinner=False)
def file_mtime(path: str) -> int:
    """mtime do arquivo (ns), cacheado para evitar muitos os.stat."""
    try:
        return os.stat(path).st_mtime_ns
    except Exception:
        return 0


@st.cache_data(show_spinner=False)
def thumbnail_data_uri(path: str, size: int, cover: bool, mtime_ns: int) -> str:
    """Gera uma miniatura quadrada PNG como data URI, cacheada por caminho+size+cover+mtime.

    - cover=True: recorta preenchendo (ImageOps.fit)
    - cover=False: mantém proporção e centraliza em canvas quadrado transparente
    """
    try:
        from PIL import Image, ImageOps  # type: ignore
        mime = 'image/png'
        with Image.open(path) as im:
            im = im.convert('RGBA')
            if cover:
                thumb = ImageOps.fit(im, (size, size), method=Image.LANCZOS)
            else:
                im.thumbnail((size, size), Image.LANCZOS)
                thumb = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                off = ((size - im.width) // 2, (size - im.height) // 2)
                thumb.paste(im, off)
        buf = io.BytesIO()
        thumb.save(buf, format='PNG', optimize=True)
        data = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:{mime};base64,{data}"
    except Exception:
        return ''


# ----------------- UI -----------------

st.set_page_config(page_title='Produção por Episódio', layout='wide')

# ---- Global CSS theme tweaks ----
st.markdown(
    """
    <style>
    :root { --svb-primary: #0d6efd; --svb-green:#198754; --svb-amber:#ffc107; --svb-red:#dc3545; --svb-gray:#6c757d; }
    .svb-header { display:flex; align-items:center; justify-content:center; gap:12px; margin: 6px 0 10px 0; }
    .svb-header img { max-height: 192px; height: auto; width: auto; max-width: 100%; display:block; }
    .svb-ep-links { margin: 10px 0 14px 0; }
    .svb-ep-links a { display:inline-block; padding:4px 10px; border:1px solid #dee2e6; border-radius:999px; margin:4px 6px 0 0; text-decoration:none; color:#0d6efd; background:#f8f9ff; }
    .svb-ep-links a:hover { background:#e9f3ff; }
        /* Tornar o menu de episódios fixo no topo (sticky) */
        .svb-ep-links { position: sticky; top: 0; z-index: 1003; padding: 6px 4px; background: rgba(255,255,255,0.9); backdrop-filter: blur(6px); border-bottom: 1px solid rgba(128,128,128,0.15); }
        /* Corrigir possíveis contenções de overflow nos painéis das tabs e container principal */
        section.main > div.block-container { overflow: visible !important; }
        div[data-testid="stTabs"] > div[role="tabpanel"] { overflow: visible !important; }
        /* Estilo de ações (expandir/recolher) na barra sticky */
        .svb-ep-links .svb-action { display:inline-block; padding:4px 10px; border:1px solid #adb5bd; border-radius:8px; margin:4px 6px 0 0; text-decoration:none; color:inherit; background:rgba(0,0,0,0.08); }
        .svb-ep-links .svb-action:hover { filter: brightness(0.95); }
        @media (prefers-color-scheme: dark) {
            .svb-ep-links { background: rgba(14,17,23,0.9); border-bottom-color: rgba(255,255,255,0.12); }
        }
        /* Ajuste de deslocamento ao navegar para âncoras dos episódios */
        [id^="episodio-"] { scroll-margin-top: 140px; }
    .svb-badge { display:inline-block; padding:3px 10px; border-radius:8px; font-size:12px; font-weight:600; border:1px solid; }
    .svb-badge.gray{ background:#f8fafc; color:#1e293b; border-color:#e2e8f0; }
    .svb-badge.green{ background:#dcfce7; color:#15803d; border-color:#bbf7d0; }
    .svb-badge.blue{ background:#dbeafe; color:#1e40af; border-color:#93c5fd; }
    .svb-badge.red{ background:#fee2e2; color:#dc2626; border-color:#fca5a5; }
    .svb-badge.amber{ background:#fef3c7; color:#d97706; border-color:#fcd34d; }
    .svb-pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid #d0d7de; color:inherit; background:rgba(0,0,0,0.06); }
    /* Cards com melhor contraste e design */
    .svb-card { border:1px solid #e2e8f0; border-radius:12px; padding:12px 16px; background:#ffffff; margin:10px 0; color:#0f172a; box-shadow:0 1px 3px 0 rgba(0, 0, 0, 0.1); transition:box-shadow 0.2s; }
    .svb-card:hover { box-shadow:0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    /* Concluídos: fundo verde suave com boa legibilidade */
    .svb-card.done { background:#f0fdf4; color:#15803d; border-color:#86efac; }
    .svb-title { font-weight:700; margin-bottom:6px; color:#0f172a; font-size:16px; }
    .svb-title code { background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; padding:2px 6px; border-radius:4px; font-size:12px; }
    .svb-links a { color:#2563eb; text-decoration:none; margin-right:10px; font-weight:500; }
    .svb-links a:hover { color:#1d4ed8; text-decoration:underline; }
    .svb-row { display:flex; gap:16px; align-items:flex-start; }
    .svb-thumb { border:2px solid #e5e7eb; border-radius:12px; background:#f8fafc; object-fit:contain; box-shadow:0 2px 4px 0 rgba(0, 0, 0, 0.1); }
    .svb-grid { display:grid; grid-template-columns: auto auto; gap:8px 16px; margin-top:8px; }
    .svb-label { font-size:13px; color:#374151; font-weight:600; margin-right:8px; }
    .svb-comment { font-size:13px; color:#4b5563; border-top:1px solid #e5e7eb; padding-top:8px; margin-top:8px; font-style:italic; }
    .svb-metrics { color:inherit; opacity:0.85; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Header logo (opcional) ----
def _find_logo_file() -> str:
    # Busca por nomes comuns e também por arquivos contendo 'logo' ou 'vilabarca' no nome.
    explicit = [
        BASE_DIR / 'logo.png', BASE_DIR / 'logo.jpg', BASE_DIR / 'logo.jpeg', BASE_DIR / 'logo.webp', BASE_DIR / 'logo.svg',
        BASE_DIR / 'assets' / 'logo.png', BASE_DIR / 'assets' / 'logo.jpg', BASE_DIR / 'assets' / 'logo.svg',
    ]
    for p in explicit:
        if p.exists():
            return str(p)
    try_dirs = [BASE_DIR, BASE_DIR / 'assets', BASE_DIR / 'static', BASE_DIR / 'images', BASE_DIR / 'imagens']
    exts = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
    for d in try_dirs:
        if not d.exists() or not d.is_dir():
            continue
        picks = []
        for p in d.iterdir():
            if p.suffix.lower() in exts:
                n = p.name.lower()
                if 'logo' in n or 'vilabarca' in n:
                    picks.append(p)
        if picks:
            # Prefer PNG over others; then by name length (more specific) and size desc
            def _score(path: Path):
                pref = 0 if path.suffix.lower() == '.png' else 1
                try:
                    stt = path.stat()
                    size = -stt.st_size  # larger first
                except Exception:
                    size = 0
                return (pref, len(path.name), size)
            picks.sort(key=_score)
            return str(picks[0])
    return ''

_logo = _find_logo_file()
if _logo:
    try:
        mt = os.stat(_logo).st_mtime_ns
    except Exception:
        mt = 0
    src = image_to_data_uri(_logo, mt)
    # Sidebar logo, centralizado, com tamanho proporcional
    st.sidebar.markdown(
        f"""
        <div style='display:flex;justify-content:center;align-items:center;margin:8px 0 16px;'>
            <img src='{src}' alt='logo' style='max-height:192px;height:auto;width:auto;max-width:100%;display:block;'>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.title('Produção por Episódio')

# Query params: controlar expandir/recolher tudo via URL (?expand=1|0)
params = st.query_params if hasattr(st, 'query_params') else {}
expand_all_from_qs = None
try:
    val = params.get('expand') if isinstance(params, dict) else None
    if isinstance(val, list):
        val = val[0] if val else None
    if val is not None:
        expand_all_from_qs = str(val) in ('1', 'true', 'True')
except Exception:
    pass
if expand_all_from_qs is not None:
    st.session_state['__expand_all__'] = expand_all_from_qs

if not CSV_PATH.exists():
    # Falha rápida caso o CSV não esteja presente na pasta do projeto
    st.error(f'CSV não encontrado: {CSV_PATH}')
    st.stop()

try:
    # Leitura do CSV (cacheada). Exibe o traceback na UI em caso de erro.
    df = load_dataframe(CSV_PATH)
except Exception as e:
    st.exception(e)
    st.stop()

_sig_images = _dir_signature(IMG_DIR)
img_index = load_images_index(_sig_images)  # Índice de imagens disponível para o resolver e atualizado quando a pasta mudar
# Guarda a assinatura na sessão e avisa quando houver atualização
_prev_sig = st.session_state.get('__img_sig__')
if _prev_sig is not None and _prev_sig != _sig_images:
    st.toast('Miniaturas atualizadas a partir da pasta personagens.', icon='🖼️')
st.session_state['__img_sig__'] = _sig_images
all_eps = detect_all_numeric_episodes(df)  # Lista de episódios distintos para seleção

# Unique values for filters
# Obtemos valores únicos para popular os multiselects de responsáveis, status e urgências
resps = sorted({v for v in pd.concat([
    df.get(COL_RESP_CONCEPT, pd.Series(dtype=str)),
    df.get(COL_RESP_RIG, pd.Series(dtype=str))
], ignore_index=True).dropna().unique().tolist()}, key=lambda s: _normalize_text(str(s)))
statuses = sorted({v for v in pd.concat([
    df.get(COL_STATUS_CONCEPT, pd.Series(dtype=str)),
    df.get(COL_STATUS_RIG, pd.Series(dtype=str))
], ignore_index=True).dropna().unique().tolist()}, key=lambda s: _normalize_text(str(s)))

# urgency order
urgs_raw = {v for v in pd.concat([
    df.get(COL_URG_CONCEPT, pd.Series(dtype=str)),
    df.get(COL_URG_RIG, pd.Series(dtype=str))
], ignore_index=True).dropna().unique().tolist()}

def _urg_key(u: str):
    nu = _normalize_text(str(u))
    if nu == 'alta':
        return (0, nu)
    if nu == 'media':
        return (1, nu)
    if nu == 'baixa':
        return (2, nu)
    return (9, nu)

urgs = sorted(urgs_raw, key=_urg_key)

# Sidebar filters
# Controles principais: busca, filtros por responsável/status/urgência, pendentes e exibição
st.sidebar.header('Filtros')
q = st.sidebar.text_input('Buscar por nome ou ID')
sel_resps = st.sidebar.multiselect('Responsáveis', options=resps)
sel_status = st.sidebar.multiselect('Status', options=statuses)
sel_urgs = st.sidebar.multiselect('Urgência', options=urgs)
only_pending = st.sidebar.checkbox('Somente pendentes (não 100%)', value=False)
hide_images = st.sidebar.checkbox('Ocultar imagens', value=False)
compact = st.sidebar.checkbox('Modo compacto', value=False)
thumb_w = st.sidebar.slider('Tamanho da miniatura', min_value=120, max_value=400, value=220, step=20)

# Image display controls (opções de aparência ocultas; usamos padrões sensatos)
thumb_mode = st.sidebar.radio('Modo da miniatura', ['Ajustada (sem corte)', 'Cortada (preencher)'], index=0)
img_cover = thumb_mode.startswith('Cortada')
img_radius = 8  # oculto

# Spacing controls (ocultos; definidos por padrão)
card_gap = (6 if compact else 10)
card_pad = (6 if compact else 10)
row_gap = 12
inner_gap = 6

# Layout selector
# Alterna entre visualização em Cards (com imagens) ou Tabela (lista compacta)
layout_mode = st.sidebar.radio('Layout', ['Cards', 'Tabela'], index=0)

# Ação rápida: forçar reindex das imagens (limpa caches e reroda)
if st.sidebar.button('Recarregar imagens', help='Reindexar a pasta personagens e atualizar miniaturas'):
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

# Auto-refresh opcional para detectar alterações na pasta periodicamente
auto_refresh = st.sidebar.checkbox('Atualizar automaticamente', value=False, help='Recarrega a página periodicamente para detectar mudanças nas imagens')
if auto_refresh:
    interval = st.sidebar.slider('Intervalo de atualização (segundos)', 5, 120, 20, 5)
    if st_autorefresh:
        st_autorefresh(interval=interval * 1000, key='__img_autorefresh__')
    else:
        st.sidebar.info("Para auto-refresh, instale: pip install streamlit-autorefresh")

# Avisos sobre a pasta de imagens (após conhecermos hide_images)
if not hide_images:
    if not IMG_DIR.exists():
        st.info("Pasta de imagens 'personagens' não encontrada ao lado do app.")
    elif len(img_index) == 0:
        st.info("Nenhuma imagem encontrada em 'personagens'.")

# Dynamic CSS from controls
# CSS dinâmico: aplicado conforme escolhas do usuário (espaçamentos, imagem, etc.)
st.markdown(f"""
<style>
.svb-row {{ gap: {row_gap}px; }}
.svb-grid {{ gap: {inner_gap}px 12px; }}
.svb-card {{ margin: {card_gap}px 0; padding: {card_pad}px {card_pad + 2}px; }}
.svb-thumb {{ border-radius: {img_radius}px; box-shadow: none; }}
.svb-thumb.cover {{ object-fit: cover; }}
</style>
""", unsafe_allow_html=True)

# Episode selection
show_all = st.sidebar.checkbox('Mostrar todos os episódios', value=True)
selected_ep = None
if not show_all:
    selected_ep = st.sidebar.selectbox('Episódio', options=all_eps, index=0 if all_eps else None)

# Explode episodes for grouping — versão cacheada e pré-processada
base_exp = build_base_exp(df, tuple(all_eps))
exp = base_exp.copy()

# Filters apply
# Aplicamos busca e filtros de forma cumulativa usando funções auxiliares
q_norm = ''.join(ch for ch in unidecode((q or '').lower()) if ch.isalnum())
if q_norm:
    exp = exp[(exp['__name_norm__'].str.contains(q_norm)) | (exp['__id_norm__'].str.contains(q_norm))]

if sel_resps:
    sr_norm = {_normalize_text(x) for x in sel_resps}
    def _resp_match(row):
        return (_normalize_text(row.get(COL_RESP_CONCEPT,'')) in sr_norm) or (_normalize_text(row.get(COL_RESP_RIG,'')) in sr_norm)
    exp = exp[exp.apply(_resp_match, axis=1)]

if sel_status:
    ss_norm = {_normalize_text(x) for x in sel_status}
    def _status_match(row):
        return (_normalize_text(row.get(COL_STATUS_CONCEPT,'')) in ss_norm) or (_normalize_text(row.get(COL_STATUS_RIG,'')) in ss_norm)
    exp = exp[exp.apply(_status_match, axis=1)]

if sel_urgs:
    su_norm = {_normalize_text(x) for x in sel_urgs}
    def _urg_match(row):
        return (_normalize_text(row.get(COL_URG_CONCEPT,'')) in su_norm) or (_normalize_text(row.get(COL_URG_RIG,'')) in su_norm)
    exp = exp[exp.apply(_urg_match, axis=1)]

if only_pending:
    exp = exp[~exp['__ok_both__']]

def render_dashboard():
    """Renderiza a aba principal de produção por episódio (chips + expanders)."""
    # Agrupamento final por episódio com chips âncora e expander por episódio
    if not all_eps:
        st.info('Nenhum episódio numérico encontrado no CSV.')
        return
    eps_to_show = all_eps if show_all else ([selected_ep] if selected_ep is not None else [])
    if not eps_to_show:
        st.info('Selecione um episódio na barra lateral.')
        return
    # Episode chips — barra fixa (sticky) no topo
    st.markdown('<div class="svb-ep-links">' + ' '.join([f"<a href='#episodio-{ep}'>Ep {ep}</a>" for ep in eps_to_show]) + '</div>', unsafe_allow_html=True)

    # Expandir/Recolher tudo
    # Botões (não abrem nova aba). Mantidos abaixo da barra sticky
    cexp1, cexp2, _ = st.columns([0.15, 0.18, 0.67])
    with cexp1:
        if st.button('Expandir tudo', key='expand_all_btn'):
            st.session_state['__expand_all__'] = True
            try:
                st.query_params['expand'] = '1'
            except Exception:
                pass
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()
    with cexp2:
        if st.button('Recolher tudo', key='collapse_all_btn'):
            st.session_state['__expand_all__'] = False
            try:
                st.query_params['expand'] = '0'
            except Exception:
                pass
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

    for ep in eps_to_show:
        bloco = exp[exp['__EP_LIST__'] == ep].copy()
        total_ep = len(bloco)
        concept_done = int((bloco[COL_STATUS_CONCEPT].map(is_concluido)).sum())
        rig_done = int((bloco[COL_STATUS_RIG].map(is_concluido)).sum())
        both_done = int(((bloco[COL_STATUS_CONCEPT].map(is_concluido)) & (bloco[COL_STATUS_RIG].map(is_concluido))).sum())

        # Âncora única por episódio (antes do expander) para evitar IDs duplicados
        st.markdown(f"<div id='episodio-{ep}'></div>", unsafe_allow_html=True)
        with st.expander(f"Episódio {ep} — {total_ep} ", expanded=st.session_state.get('__expand_all__', False)):
            st.markdown(f"<span class='svb-metrics'>Concept: <b>{concept_done}</b>/{total_ep} • Rig: <b>{rig_done}</b>/{total_ep} • Ambos: <b>{both_done}</b>/{total_ep}</span>", unsafe_allow_html=True)
            # Sort options
            # O usuário escolhe a ordenação do bloco atual (nome, ID, urgências, status, responsáveis)
            sort_key = st.selectbox(
                'Ordenar por',
                options=['Nome','ID','Urgência Concept','Urgência Rig','Status Concept','Status Rig','Resp. Concept','Resp. Rig'],
                key=f'sort_ep_{ep}',
                index=0
            )
            sort_map = {
                'Nome': COL_NAME,
                'ID': COL_FILE_ID,
                'Urgência Concept': COL_URG_CONCEPT,
                'Urgência Rig': COL_URG_RIG,
                'Status Concept': COL_STATUS_CONCEPT,
                'Status Rig': COL_STATUS_RIG,
                'Resp. Concept': COL_RESP_CONCEPT,
                'Resp. Rig': COL_RESP_RIG,
            }
            bloco.sort_values(by=sort_map.get(sort_key, COL_NAME), inplace=True, key=lambda s: s.astype(str).str.lower())

            if layout_mode == 'Tabela':
                # Visualização compacta em DataFrame
                view = bloco[[COL_NAME, COL_FILE_ID, COL_RESP_CONCEPT, COL_URG_CONCEPT, COL_STATUS_CONCEPT, COL_RESP_RIG, COL_URG_RIG, COL_STATUS_RIG, COL_COMMENTS]].copy()
                view.rename(columns={
                    COL_NAME:'Nome', COL_FILE_ID:'ID', COL_RESP_CONCEPT:'Resp Concept', COL_URG_CONCEPT:'Urg Concept', COL_STATUS_CONCEPT:'Status Concept',
                    COL_RESP_RIG:'Resp Rig', COL_URG_RIG:'Urg Rig', COL_STATUS_RIG:'Status Rig', COL_COMMENTS:'Comentários'
                }, inplace=True)
                view['Concluído'] = (view['Status Concept'].map(is_concluido)) & (view['Status Rig'].map(is_concluido))
                st.dataframe(view, use_container_width=True, hide_index=True)
            else:
                # Render cards (layout visual com miniatura e badges/pills)
                for _, r in bloco.iterrows():
                    nm = coalesce(r.get(COL_NAME))
                    fid = coalesce(r.get(COL_FILE_ID))
                    rig_link = coalesce(r.get(COL_RIG_LINK))
                    concept_link = coalesce(r.get(COL_CONCEPT_LINK))
                    sync_link = coalesce(r.get(COL_SYNCSKETCH))
                    resp_c = coalesce(r.get(COL_RESP_CONCEPT))
                    urg_c = coalesce(r.get(COL_URG_CONCEPT))
                    sta_c = coalesce(r.get(COL_STATUS_CONCEPT))
                    resp_r = coalesce(r.get(COL_RESP_RIG))
                    urg_r = coalesce(r.get(COL_URG_RIG))
                    sta_r = coalesce(r.get(COL_STATUS_RIG))
                    comments = coalesce(r.get(COL_COMMENTS))

                    # Image resolve — tenta casar por ID e nome com o índice gerado da pasta `personagens`
                    img_path = ''
                    try:
                        img_path = find_image_for(img_index, fid, nm)
                    except Exception:
                        img_path = ''

                    ok_both = is_concluido(sta_c) and is_concluido(sta_r)
                    done_cls = 'done' if ok_both else ''
                    # Classes for status — definem as cores das badges de Status/Urgência
                    def _status_cls(s):
                        n = _normalize_text(s)
                        if n == 'concluido': return 'green'
                        if n in ('em andamento','fazendo','andamento'): return 'blue'
                        if n in ('a fazer','pendente','todo'): return 'gray'
                        if n in ('bloqueado','impedido'): return 'red'
                        return 'amber'
                    def _urg_cls(u):
                        n = _normalize_text(u)
                        if n == 'alta': return 'red'
                        if n == 'media': return 'amber'
                        if n == 'baixa': return 'green'
                        return 'gray'
                    # Color for responsible pill via simple hash hue — cria um tom por responsável
                    def _resp_style(name: str):
                        s = norm_key(name or '')
                        h = 0
                        for ch in s:
                            h = (h*31 + ord(ch)) & 0xFFFFFFFF
                        hue = h % 360
                        return f"background:hsl({hue},70%,92%);border-color:#d0d7de;"

                    # Build HTML card — HTML inline para maior controle visual (imagens, badges, grid)
                    left_img = ''
                    if not hide_images:
                        # Usa data URI para imagens locais; cacheado por mtime
                        if img_path:
                            try:
                                mt = os.stat(img_path).st_mtime_ns
                            except Exception:
                                mt = 0
                            src = image_to_data_uri(img_path, mt)
                        else:
                            src = 'https://via.placeholder.com/192x192.png?text=Sem+Imagem'
                        cover_cls = ' cover' if img_cover else ''
                        left_img = f"<img src='{src}' class='svb-thumb{cover_cls}' width='{thumb_w}' height='{thumb_w}'>"
                    # Padding do conteúdo do card: respeita modo compacto
                    pad = f"{card_pad}px" if not compact else f"{min(card_pad, 10)}px"
                    html_card = f"""
                    <div class='svb-card {done_cls}'>
                        <div class='svb-row'>
                            {left_img}
                            <div style='flex:1 1 auto;padding:{pad};'>
                                <div class='svb-title'>{nm} <code>{fid}</code></div>
                                <div class='svb-links'>
                                    {f"<a href='{rig_link}' target='_blank'>Rig</a>" if rig_link else ''}
                                    {f"<a href='{concept_link}' target='_blank'>Concept</a>" if concept_link else ''}
                                    {f"<a href='{sync_link}' target='_blank'>SyncSketch</a>" if sync_link else ''}
                                </div>
                                <div class='svb-grid' style='margin-top:6px;'>
                                    <div><span class='svb-label'>Concept</span> <span class='svb-pill' style='{_resp_style(resp_c)}'>{resp_c or '—'}</span></div>
                                    <div><span class='svb-badge {_urg_cls(urg_c)}'>{urg_c or '—'}</span> <span class='svb-badge {_status_cls(sta_c)}'>{sta_c or '—'}</span></div>
                                    <div><span class='svb-label'>Rig</span> <span class='svb-pill' style='{_resp_style(resp_r)}'>{resp_r or '—'}</span></div>
                                    <div><span class='svb-badge {_urg_cls(urg_r)}'>{urg_r or '—'}</span> <span class='svb-badge {_status_cls(sta_r)}'>{sta_r or '—'}</span></div>
                                </div>
                                <div class='svb-comment'>{comments or '—'}</div>
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(html_card, unsafe_allow_html=True)

    st.caption('UI em Streamlit — filtros reativos, colapsáveis por episódio, ordenação, e destaque visual para concluídos, urgência e responsáveis.')

# Abas: Dashboard, Estatísticas, Histórico, Lista
tab_main, tab_stats, tab_hist, tab_list = st.tabs(['Dashboard', 'Estatísticas', 'Histórico', 'Lista'])
with tab_main:
    render_dashboard()

with tab_stats:
    import altair as alt  # import tardio para reduzir tempo de carregamento inicial
    st.subheader('Visão geral')
    ov = overall_stats(df, COL_STATUS_CONCEPT, COL_STATUS_RIG, is_concluido, id_col=COL_FILE_ID, name_col=COL_NAME)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Personagens', ov['total'])
    c2.metric('Concept concluído', ov['concept_done'], f"{ov['concept_pct']:.0f}%")
    c3.metric('Rig concluído', ov['rig_done'], f"{ov['rig_pct']:.0f}%")
    c4.metric('Ambos concluídos', ov['both_done'], f"{ov['both_pct']:.0f}%")

    st.divider()
    st.subheader('Conclusão por episódio')
    ep_df = episode_completion(exp, COL_STATUS_CONCEPT, COL_STATUS_RIG, is_concluido, id_col=COL_FILE_ID, name_col=COL_NAME)
    st.dataframe(ep_df, use_container_width=True, hide_index=True)
    st.bar_chart(ep_df.set_index('Episódio')['% Ambos'])

    st.divider()
    st.subheader('Distribuição de Status')
    st.caption('Separado por etapa (Concept / Rig)')
    s_conc, s_rig = status_breakdown(df, COL_STATUS_CONCEPT, COL_STATUS_RIG, id_col=COL_FILE_ID, name_col=COL_NAME)
    cc, cr = st.columns(2)
    # Donut charts for status
    def donut_chart(df_src, label_col, title):
        df_plot = df_src.copy()
        if df_plot.empty:
            return None
        df_plot = df_plot[df_plot['count'] > 0]
        return alt.Chart(df_plot).mark_arc(innerRadius=60, outerRadius=100).encode(
            theta=alt.Theta(field='count', type='quantitative'),
            color=alt.Color(field=label_col, type='nominal', legend=alt.Legend(title=label_col))
        ).properties(width=280, height=220, title=title)

    ch1 = donut_chart(s_conc, COL_STATUS_CONCEPT, 'Status — Concept')
    ch2 = donut_chart(s_rig, COL_STATUS_RIG, 'Status — Rig')
    if ch1 is not None:
        cc.altair_chart(ch1, use_container_width=True)
    else:
        cc.info('Sem dados de Status (Concept)')
    if ch2 is not None:
        cr.altair_chart(ch2, use_container_width=True)
    else:
        cr.info('Sem dados de Status (Rig)')
    # Optional: tables below
    st.caption('Tabelas')
    t1, t2 = st.columns(2)
    t1.dataframe(s_conc, use_container_width=True)
    t2.dataframe(s_rig, use_container_width=True)

    st.divider()
    st.subheader('Urgência')
    u_conc, u_rig = urgency_breakdown(df, COL_URG_CONCEPT, COL_URG_RIG, id_col=COL_FILE_ID, name_col=COL_NAME)
    uc, ur = st.columns(2)
    # Donut charts for urgency
    ch3 = donut_chart(u_conc, COL_URG_CONCEPT, 'Urgência — Concept')
    ch4 = donut_chart(u_rig, COL_URG_RIG, 'Urgência — Rig')
    if ch3 is not None:
        uc.altair_chart(ch3, use_container_width=True)
    else:
        uc.info('Sem dados de Urgência (Concept)')
    if ch4 is not None:
        ur.altair_chart(ch4, use_container_width=True)
    else:
        ur.info('Sem dados de Urgência (Rig)')
    st.caption('Tabelas')
    u1, u2 = st.columns(2)
    u1.dataframe(u_conc, use_container_width=True)
    u2.dataframe(u_rig, use_container_width=True)

    st.divider()
    st.subheader('Responsáveis (Top 10)')
    r_conc, r_rig = responsavel_breakdown(df, COL_RESP_CONCEPT, COL_RESP_RIG, top=10, id_col=COL_FILE_ID, name_col=COL_NAME)
    rc, rr = st.columns(2)
    rc.dataframe(r_conc, use_container_width=True)
    rr.dataframe(r_rig, use_container_width=True)

    with tab_hist:
        render_timeline_tab(df)
    with tab_list:
        def _thumb_for(fid: str, name: str, size: int = 56) -> str:
            path = find_image_for(img_index, fid, name)
            if not path:
                return ''
            mt = file_mtime(path)
            return thumbnail_data_uri(path, size=size, cover=True, mtime_ns=mt)
        render_list_tab(df, get_thumb=_thumb_for)
