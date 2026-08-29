#!/usr/bin/env python
# coding: utf-8

# Cores do plotly
import plotly.express as px

# Fontes do Tema
FONTE_GRAFICOS = "Source Sans Pro"
FONTE_TAMANHO = 14

# Paleta de Cores: D3
# https://plotly.com/python/discrete-color/

PALETA_CORES = px.colors.qualitative.D3

# Cores Notáveis
COR_SUCESSO = px.colors.qualitative.D3[2]
COR_ALERTA = px.colors.qualitative.D3[1]
COR_ERRO = px.colors.qualitative.D3[3]
COR_NULL = px.colors.qualitative.D3[7]
