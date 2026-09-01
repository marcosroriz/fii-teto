#!/usr/bin/env python
# coding: utf-8

# Página do histórico trimestral de rendimento dos fundos imobiliários

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

import tema
from calculos import calcular_historico_trimestral
from dados_mercado import obter_historico_fii, obter_indices_historicos
from fii_tickers import FII_TICKERS

ALIQUOTA_IR = 22.5
PREMIO_IPCA_SETE = 7.0
PREMIO_IPCA_OITO = 8.0
TR_MENSAL = 0.1693
FII_OPTIONS = [{"label": ticker, "value": f"{ticker}.SA"} for ticker in FII_TICKERS]


def taxa_selic_liquida(selic: float) -> float:
    mensal_bruta = (1 + selic / 100) ** (1 / 12) - 1
    mensal_liquida = mensal_bruta * (1 - ALIQUOTA_IR / 100)
    return ((1 + mensal_liquida) ** 12 - 1) * 100


def taxa_poupanca(selic: float, tr_mensal: float = TR_MENSAL) -> float:
    if selic > 8.5:
        rendimento_mensal = 0.5 / 100 + tr_mensal / 100
    else:
        rendimento_mensal = (1 + (selic * 0.7) / 100) ** (1 / 12) - 1
        rendimento_mensal += tr_mensal / 100
    return ((1 + rendimento_mensal) ** 12 - 1) * 100


def adicionar_indices(pontos: pd.DataFrame, selic: pd.Series, ipca: pd.Series) -> pd.DataFrame:
    """Alinha os índices conhecidos em cada data trimestral do FII."""
    fator_liquido = 1 - ALIQUOTA_IR / 100
    linhas = []
    for ponto in pontos.to_dict("records"):
        data = pd.Timestamp(ponto["data"])
        selic_ate_data = selic.loc[selic.index <= data]
        ipca_ate_data = ipca.loc[ipca.index <= data].tail(12)
        if selic_ate_data.empty or len(ipca_ate_data) < 12:
            continue
        selic_bruta = float(selic_ate_data.iloc[-1])
        ipca_12m = ((1 + ipca_ate_data / 100).prod() - 1) * 100
        linhas.append(
            {
                **ponto,
                "selic_liquida": taxa_selic_liquida(selic_bruta),
                "poupanca": taxa_poupanca(selic_bruta),
                "ipca_mais_sete_liquido": (ipca_12m + PREMIO_IPCA_SETE) * fator_liquido,
                "ipca_mais_oito_liquido": (ipca_12m + PREMIO_IPCA_OITO) * fator_liquido,
            }
        )
    return pd.DataFrame(linhas)


def criar_grafico(pontos: pd.DataFrame, ticker: str) -> go.Figure:
    colunas_taxas = [
        "dy_anualizado",
        "selic_liquida",
        "poupanca",
        "ipca_mais_oito_liquido",
        "ipca_mais_sete_liquido",
    ]
    menor_taxa = pontos[colunas_taxas].min().min()
    maior_taxa = pontos[colunas_taxas].max().max()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pontos["data"],
            y=pontos["dy_anualizado"],
            name=f"{ticker} · DY 3m anualizado",
            mode="lines+markers",
            line={"color": tema.PALETA_CORES[0], "width": 3},
            marker={"size": 9},
            customdata=pontos[["preco", "proventos_trimestre"]],
            hovertemplate=(
                "<b>%{x|%d/%m/%Y}</b><br>"
                "DY anualizado: %{y:.2f}%<br>"
                "Cotação: R$ %{customdata[0]:.2f}<br>"
                "Três últimos proventos: R$ %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )
    referencias = [
        ("selic_liquida", "SELIC líquida", tema.COR_SUCESSO),
        ("poupanca", "Poupança", tema.COR_NULL),
        ("ipca_mais_oito_liquido", "IPCA + 8% líquido", tema.COR_ALERTA),
        ("ipca_mais_sete_liquido", "IPCA + 7% líquido", tema.COR_ERRO),
    ]
    for coluna, nome, cor in referencias:
        fig.add_trace(
            go.Scatter(
                x=pontos["data"],
                y=pontos[coluna],
                name=nome,
                mode="lines+markers",
                line={"color": cor, "width": 2, "dash": "dash"},
                marker={"size": 7},
                hovertemplate=f"<b>%{{x|%d/%m/%Y}}</b><br>{nome}: %{{y:.2f}}%<extra></extra>",
            )
        )
    fig.update_layout(
        height=650,
        margin={"l": 65, "r": 20, "t": 35, "b": 55},
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "Trimestre", "tickformat": "%m/%Y", "dtick": "M3"},
        yaxis={
            "title": "Taxa líquida anual (%)",
            "ticksuffix": "%",
            "range": [menor_taxa - 2, maior_taxa + 2],
            "gridcolor": "#e2e8e5",
        },
    )
    return fig


layout = dbc.Container(
    [
        html.Div(
            [
                html.Div("HISTÓRICO DE RENDA", className="eyebrow"),
                html.H1("Histórico do fundo imobiliário", className="display-6 fw-bold"),
                html.P(
                    "Compare o dividend yield dos três últimos proventos, anualizado, com a poupança, "
                    "a SELIC, o IPCA + 7% e o IPCA + 8% ao longo dos últimos três anos.",
                    className="lead text-secondary",
                ),
            ],
            className="py-4",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H4("Configure a análise", className="mb-4"),
                                html.Label("Fundo imobiliário", className="fw-semibold"),
                                dcc.Dropdown(
                                    id="historico-fii-dropdown",
                                    options=FII_OPTIONS,
                                    value="HGLG11.SA",
                                    searchable=True,
                                    clearable=False,
                                    maxHeight=400,
                                    className="mb-4",
                                ),
                                dbc.Button(
                                    [DashIconify(icon="solar:history-linear", width=20), " Consultar histórico"],
                                    id="historico-calcular-button",
                                    color="primary",
                                    size="lg",
                                    className="w-100",
                                ),
                                html.Small(
                                    "Cotações e proventos: Yahoo Finance. Índices: Banco Central do Brasil. "
                                    f"TR mensal considerada: {TR_MENSAL:.4f}%.",
                                    id="historico-fonte",
                                    className="d-block text-muted mt-3",
                                ),
                            ]
                        ),
                        className="shadow-sm border-0 config-card",
                    ),
                    lg=4,
                    className="mb-4",
                ),
                dbc.Col(
                    [
                        dbc.Alert(id="historico-erro", color="danger", is_open=False),
                        html.Div(id="historico-resumo", className="mb-3"),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Rendimento anualizado a cada três meses", className="mb-1"),
                                    html.P(id="historico-descricao", className="text-muted"),
                                    dcc.Loading(
                                        dcc.Graph(
                                            id="grafico-historico",
                                            config={"displayModeBar": False},
                                        )
                                    ),
                                ]
                            ),
                            className="shadow-sm border-0",
                        ),
                    ],
                    lg=8,
                ),
            ],
            className="pb-5",
        ),
    ],
    fluid=True,
    className="page-wrap",
)


@callback(
    Output("grafico-historico", "figure"),
    Output("historico-resumo", "children"),
    Output("historico-descricao", "children"),
    Output("historico-erro", "children"),
    Output("historico-erro", "is_open"),
    Input("historico-calcular-button", "n_clicks"),
    State("historico-fii-dropdown", "value"),
    prevent_initial_call=False,
)
def carregar_historico(_clicks, symbol):
    try:
        hoje = pd.Timestamp.today().normalize()
        inicio = hoje - pd.DateOffset(years=3)
        inicio_fii = inicio - pd.DateOffset(months=3)
        inicio_indices = inicio - pd.DateOffset(months=12)
        fim_consulta = hoje + pd.Timedelta(days=1)

        history, nome = obter_historico_fii(
            symbol,
            inicio_fii.strftime("%Y-%m-%d"),
            fim_consulta.strftime("%Y-%m-%d"),
        )
        selic, ipca = obter_indices_historicos(
            inicio_indices.strftime("%Y-%m-%d"),
            hoje.strftime("%Y-%m-%d"),
        )
        pontos_fii = calcular_historico_trimestral(history, inicio, hoje)
        pontos = adicionar_indices(pontos_fii, selic, ipca)
        if pontos.empty:
            raise ValueError("não há dados trimestrais suficientes para montar o gráfico")

        ticker = symbol.removesuffix(".SA")
        ultimo = pontos.iloc[-1]
        resumo = dbc.Row(
            [
                dbc.Col(
                    dbc.Alert(f"{ticker}: {ultimo['dy_anualizado']:.2f}% a.a.", color="primary"),
                    md=3,
                ),
                dbc.Col(
                    dbc.Alert(f"SELIC: {ultimo['selic_liquida']:.2f}%", color="success"),
                    md=3,
                ),
                dbc.Col(
                    dbc.Alert(f"IPCA + 8%: {ultimo['ipca_mais_oito_liquido']:.2f}%", color="warning"),
                    md=3,
                ),
                dbc.Col(
                    dbc.Alert(f"IPCA + 7%: {ultimo['ipca_mais_sete_liquido']:.2f}%", color="danger"),
                    md=3,
                ),
            ],
            className="g-2",
        )
        descricao = (
            f"{nome} · {ticker} · de {pontos.iloc[0]['data']:%d/%m/%Y} "
            f"até {pontos.iloc[-1]['data']:%d/%m/%Y}."
        )
        return criar_grafico(pontos, ticker), resumo, descricao, "", False
    except Exception as exc:
        vazio = go.Figure()
        vazio.update_layout(
            annotations=[{"text": "Não foi possível carregar o histórico", "showarrow": False}],
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return vazio, "", "", f"Falha ao consultar o histórico: {exc}.", True


dash.register_page(
    __name__, name="Histórico", path="/historico", title="Histórico de FIIs"
)
