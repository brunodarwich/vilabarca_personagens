"""
Métricas e estatísticas da produção.

Este módulo concentra a lógica de cálculo para ser reutilizada na aba de Estatísticas.
"""
from __future__ import annotations
from typing import Callable, Tuple, Optional
import re
import unicodedata
import pandas as pd


def _pct(part: int, total: int) -> float:
    return (part / total * 100.0) if total else 0.0


def _norm_key(s: str) -> str:
    if s is None:
        return ''
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '', s)


def _dedup_df(df: pd.DataFrame, id_col: Optional[str], name_col: Optional[str]) -> pd.DataFrame:
    """Remove duplicidades por personagem usando ID (preferencial) ou Nome normalizado."""
    if (id_col and id_col in df.columns) or (name_col and name_col in df.columns):
        keys = []
        for _, row in df.iterrows():
            kid = _norm_key(row.get(id_col, '')) if id_col else ''
            knm = _norm_key(row.get(name_col, '')) if name_col else ''
            keys.append(kid or knm)
        dfx = df.copy()
        dfx['__UNIQ__'] = keys
        dfx = dfx.drop_duplicates(subset='__UNIQ__')
        return dfx
    return df


def overall_stats(df: pd.DataFrame, col_status_conc: str, col_status_rig: str, is_concluido: Callable[[str], bool], id_col: Optional[str] = None, name_col: Optional[str] = None) -> dict:
    """Resumo geral: totais e percentuais por etapa e ambos."""
    dfx = _dedup_df(df, id_col, name_col)
    total = len(dfx)
    conc_done = int(dfx[col_status_conc].map(is_concluido).sum()) if col_status_conc in dfx.columns else 0
    rig_done = int(dfx[col_status_rig].map(is_concluido).sum()) if col_status_rig in dfx.columns else 0
    both_done = int(((dfx[col_status_conc].map(is_concluido)) & (dfx[col_status_rig].map(is_concluido))).sum()) if (col_status_conc in dfx.columns and col_status_rig in dfx.columns) else 0
    return {
        'total': total,
        'concept_done': conc_done,
        'rig_done': rig_done,
        'both_done': both_done,
        'concept_pct': _pct(conc_done, total),
        'rig_pct': _pct(rig_done, total),
        'both_pct': _pct(both_done, total),
    }


def episode_completion(exp_df: pd.DataFrame, col_status_conc: str, col_status_rig: str, is_concluido: Callable[[str], bool], id_col: Optional[str] = None, name_col: Optional[str] = None) -> pd.DataFrame:
    """Conclusão por episódio a partir do DataFrame expandido (uma linha por episódio)."""
    if '__EP_LIST__' not in exp_df.columns:
        return pd.DataFrame(columns=['Episódio', 'Qtd', 'Concept', 'Rig', 'Ambos', '% Ambos'])
    # Deduplicar por personagem dentro de cada episódio
    dfl = []
    for ep, sub in exp_df.groupby('__EP_LIST__'):
        sub_dedup = _dedup_df(sub, id_col, name_col)
        sub_dedup = sub_dedup.copy()
        sub_dedup['__EP_LIST__'] = ep
        dfl.append(sub_dedup)
    base = pd.concat(dfl, ignore_index=True) if dfl else exp_df.copy()
    g = base.groupby('__EP_LIST__')
    rows = []
    for ep, sub in g:
        total = len(sub)
        c = int(sub[col_status_conc].map(is_concluido).sum())
        r = int(sub[col_status_rig].map(is_concluido).sum())
        b = int(((sub[col_status_conc].map(is_concluido)) & (sub[col_status_rig].map(is_concluido))).sum())
        rows.append({'Episódio': ep, 'Qtd': total, 'Concept': c, 'Rig': r, 'Ambos': b, '% Ambos': _pct(b, total)})
    return pd.DataFrame(rows).sort_values('Episódio')


def _count_by(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return pd.DataFrame(columns=[col, 'count']).astype({col: 'string', 'count': 'int'})
    s = df[col].fillna('')
    out = s.value_counts(dropna=False).rename_axis(col).reset_index(name='count')
    return out


def status_breakdown(df: pd.DataFrame, col_status_conc: str, col_status_rig: str, id_col: Optional[str] = None, name_col: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Contagem por status em cada etapa."""
    dfx = _dedup_df(df, id_col, name_col)
    return _count_by(dfx, col_status_conc), _count_by(dfx, col_status_rig)


def urgency_breakdown(df: pd.DataFrame, col_urg_conc: str, col_urg_rig: str, id_col: Optional[str] = None, name_col: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Contagem por urgência em cada etapa."""
    dfx = _dedup_df(df, id_col, name_col)
    return _count_by(dfx, col_urg_conc), _count_by(dfx, col_urg_rig)


def responsavel_breakdown(df: pd.DataFrame, col_resp_conc: str, col_resp_rig: str, top: int = 10, id_col: Optional[str] = None, name_col: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Top responsáveis por volume de itens."""
    dfx = _dedup_df(df, id_col, name_col)
    rc = _count_by(dfx, col_resp_conc).head(top)
    rr = _count_by(dfx, col_resp_rig).head(top)
    return rc, rr
