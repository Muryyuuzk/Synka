#!/usr/bin/env bash
# Executa o dashboard Streamlit a partir da raiz do projeto.
# PYTHONPATH=. garante que 'app' e 'synka_lens' sejam importaveis
# de forma consistente com o pytest (mesmo contexto de import).
PYTHONPATH=. uv run streamlit run app/dashboard.py
