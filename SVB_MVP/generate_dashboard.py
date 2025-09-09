"""
Script legado (OBSOLETO): o dashboard agora é um aplicativo Streamlit.

Use: streamlit run app.py

Este arquivo foi mantido apenas como marcador para evitar confusão em ambientes
que ainda referenciam o gerador HTML antigo.
"""

from __future__ import annotations
import sys


def main() -> int:
    print("[OBSOLETO] Use o app Streamlit: app.py\n\n"
          "Como executar:\n"
          "  1) Ative a venv (opcional)\n"
          "  2) streamlit run app.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
