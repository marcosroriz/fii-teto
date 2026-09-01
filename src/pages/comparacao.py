#!/usr/bin/env python
# coding: utf-8

# Página de comparação do dividend yield recente de múltiplos FIIs

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
import plotly.graph_objects as go

import tema
from dados_mercado import obter_fii, obter_indices
from fii_tickers import FII_TICKERS

ALIQUOTA_IR = 22.5
PREMIO_IPCA_SETE = 7.0
PREMIO_IPCA = 8.0
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


def criar_grafico(
    resultados,
    selic_liquida: float,
    ipca_mais_sete_liquido: float,
    ipca_mais_oito_liquido: float,
    poupanca: float | None = None,
):
    ordenados = sorted(resultados, key=lambda item: item["dy"], reverse=True)
    padrao_deslocamentos = [-0.18, 0.18, -0.11, 0.11, 0, -0.24, 0.24, -0.15, 0.15, 0]
    deslocamentos = [
        padrao_deslocamentos[indice % len(padrao_deslocamentos)]
        for indice in range(len(ordenados))
    ]
    cores = [
        (
            tema.COR_SUCESSO
            if item["dy"] >= selic_liquida
            else tema.COR_ALERTA
            if item["dy"] >= ipca_mais_oito_liquido
            else tema.COR_ERRO
            if item["dy"] >= ipca_mais_sete_liquido
            else tema.COR_NULL
        )
        for item in ordenados
    ]
    fig = go.Figure(
        go.Scatter(
            x=deslocamentos,
            y=[item["dy"] for item in ordenados],
            mode="markers+text",
            text=[item["symbol"] for item in ordenados],
            textposition="middle right",
            customdata=[[item["nome"], item["preco"], item["proventos"]] for item in ordenados],
            hovertemplate=(
                "<b>%{text}</b><br>%{customdata[0]}<br>"
                "DY líquido: %{y:.2f}% a.a.<br>"
                "Cotação: R$ %{customdata[1]:.2f}<br>"
                "Proventos 3m anualizados: R$ %{customdata[2]:.2f}<extra></extra>"
            ),
            marker={"size": 16, "color": cores, "line": {"color": "white", "width": 2}},
        )
    )
    linhas = [
        (selic_liquida, f"SELIC líquida ({selic_liquida:.2f}%)", tema.COR_SUCESSO),
        (
            ipca_mais_sete_liquido,
            f"IPCA + 7% líquido ({ipca_mais_sete_liquido:.2f}%)",
            tema.COR_ERRO,
        ),
        (
            ipca_mais_oito_liquido,
            f"IPCA + 8% líquido ({ipca_mais_oito_liquido:.2f}%)",
            tema.COR_ALERTA,
        ),
    ]
    if poupanca is not None:
        linhas.append(
            (poupanca, f"Poupança ({poupanca:.2f}%)", tema.COR_NULL)
        )
    for taxa, rotulo, cor in linhas:
        fig.add_hline(
            y=taxa,
            line_color=cor,
            line_width=2,
            line_dash="dash",
            annotation_text=rotulo,
            annotation_position="top left",
        )
    valores = [item["dy"] for item in ordenados] + [
        taxa for taxa, _rotulo, _cor in linhas
    ]
    margem = max(1.5, (max(valores) - min(valores)) * 0.15)
    fig.update_layout(
        height=650,
        margin={"l": 65, "r": 20, "t": 45, "b": 35},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"visible": False, "range": [-0.32, 0.42], "fixedrange": True},
        yaxis={
            "title": "Taxa líquida anual (%)",
            "ticksuffix": "%",
            "range": [max(0, min(valores) - margem), max(valores) + margem],
            "gridcolor": "#e2e8e5",
        },
    )
    return fig


layout = dbc.Container(
    [
        html.Div(
            [
                html.Div("COMPARAÇÃO DE RENDA", className="eyebrow"),
                html.H1("Compare fundos imobiliários", className="display-6 fw-bold"),
                html.P(
                    "Veja o dividend yield baseado nos últimos três meses, anualizado, "
                    "contra a poupança, a SELIC, o IPCA + 7% e o IPCA + 8% líquidos de IR.",
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
                                html.Label("Fundos imobiliários", className="fw-semibold mb-2"),
                                dcc.Dropdown(
                                    id="comparacao-tickers",
                                    options=FII_OPTIONS,
                                    value=[
                                        "HGLG11.SA",
                                        "BTLG11.SA",
                                        "XPLG11.SA",
                                        "PMLL11.SA",
                                        "XPML11.SA",
                                        "KNCR11.SA",
                                        "XPCI11.SA",
                                        "BTCI11.SA",
                                        "FATN11.SA",
                                        "HGCR11.SA",
                                    ],
                                    multi=True,
                                    searchable=True,
                                    maxHeight=400,
                                    placeholder="Selecione os tickers",
                                ),
                                html.Small(
                                    "Selecione um ou mais FIIs. Os dados são consultados no Yahoo Finance.",
                                    className="d-block text-muted mt-2",
                                ),
                                dbc.Button(
                                    [DashIconify(icon="solar:chart-2-linear", width=20), " Comparar"],
                                    id="comparar-button",
                                    color="primary",
                                    size="lg",
                                    className="w-100 mt-4",
                                ),
                                html.Div(id="comparacao-fonte", className="small text-muted mt-3"),
                            ]
                        ),
                        className="shadow-sm border-0 config-card",
                    ),
                    lg=4,
                    className="mb-4",
                ),
                dbc.Col(
                    [
                        dbc.Alert(id="comparacao-erro", color="danger", is_open=False),
                        html.Div(id="comparacao-resumo", className="mb-3"),
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-comparacao-tickers",
                                        config={"displayModeBar": False},
                                    )
                                )
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
    Output("grafico-comparacao-tickers", "figure"),
    Output("comparacao-resumo", "children"),
    Output("comparacao-fonte", "children"),
    Output("comparacao-erro", "children"),
    Output("comparacao-erro", "is_open"),
    Input("comparar-button", "n_clicks"),
    State("comparacao-tickers", "value"),
    prevent_initial_call=False,
)
def comparar_tickers(_clicks, symbols):
    symbols = list(dict.fromkeys(symbols or []))
    if not symbols:
        mensagem = "Selecione ao menos um ticker."
        return go.Figure(), "", "", mensagem, True

    selic, ipca, fonte = obter_indices()
    selic_liquida = taxa_selic_liquida(selic)
    poupanca = taxa_poupanca(selic)
    ipca_mais_sete_liquido = (ipca + PREMIO_IPCA_SETE) * (1 - ALIQUOTA_IR / 100)
    ipca_mais_oito_liquido = (ipca + PREMIO_IPCA) * (1 - ALIQUOTA_IR / 100)
    resultados = []
    falhas = []
    with ThreadPoolExecutor(max_workers=min(5, len(symbols))) as executor:
        futuros = {executor.submit(obter_fii, symbol): symbol for symbol in symbols}
        for futuro in as_completed(futuros):
            symbol = futuros[futuro]
            try:
                fii = futuro.result()
                resultados.append(
                    {
                        **fii,
                        "proventos": fii["proventos_3m_anualizados"],
                        "dy": fii["proventos_3m_anualizados"] / fii["preco"] * 100,
                    }
                )
            except Exception:
                falhas.append(symbol.removesuffix(".SA"))

    if not resultados:
        return go.Figure(), "", f"Índices: {fonte}.", "Não foi possível consultar os tickers.", True

    acima_selic = sum(item["dy"] >= selic_liquida for item in resultados)
    acima_ipca = sum(item["dy"] >= ipca_mais_oito_liquido for item in resultados)
    total = len(resultados)
    resumo = dbc.Row(
        [
            dbc.Col(dbc.Alert(f"{acima_selic} acima · {total - acima_selic} abaixo da SELIC", color="success"), md=6),
            dbc.Col(
                dbc.Alert(f"{acima_ipca} acima · {total - acima_ipca} abaixo do IPCA + 8%", color="secondary"), md=6
            ),
        ],
        className="g-2",
    )
    erro = f"Sem dados para: {', '.join(falhas)}." if falhas else ""
    fonte_texto = (
        f"Índices: {fonte}. SELIC {selic:.2f}% · IPCA 12m {ipca:.2f}% · "
        f"TR mensal {TR_MENSAL:.4f}% · IR considerado: {ALIQUOTA_IR:.1f}%."
    )
    return (
        criar_grafico(
            resultados,
            selic_liquida,
            ipca_mais_sete_liquido,
            ipca_mais_oito_liquido,
            poupanca,
        ),
        resumo,
        fonte_texto,
        erro,
        bool(falhas),
    )


dash.register_page(__name__, name="Comparar FIIs", path="/comparacao", title="Comparação de FIIs")
