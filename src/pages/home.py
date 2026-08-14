#!/usr/bin/env python
# coding: utf-8
"""Página principal da calculadora de preço-teto de FIIs."""

from __future__ import annotations

from functools import lru_cache
from math import prod
from typing import Any

import dash
from dash import Input, Output, State, callback, dcc, html, no_update
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify
import plotly.graph_objects as go
import requests
import yfinance as yf

from fii_tickers import FII_TICKERS


# O Yahoo Finance não oferece um endpoint de listagem completa da B3. A lista
# publicada em fii_tickers.py alimenta o dropdown e o yfinance valida/consulta o FII.
FII_OPTIONS = [{"label": ticker, "value": f"{ticker}.SA"} for ticker in FII_TICKERS]
FALLBACK_SELIC = 14.0
FALLBACK_IPCA = 5.0
INVESTIMENTO = 10_000.0
ALIQUOTA_IR = 22.5


def brl(value: float | None) -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%".replace(".", ",")


def pp(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f} p.p.".replace(".", ",")


def _safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def obter_indices() -> tuple[float, float, str]:
    """Obtém Selic meta (SGS 432) e IPCA acumulado em 12 meses (SGS 433)."""
    try:
        url = (
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/"
            "ultimos/{n}?formato=json"
        )
        headers = {"User-Agent": "fii-teto/1.0"}
        selic_data = requests.get(
            url.format(serie=432, n=1), headers=headers, timeout=5
        ).json()
        ipca_data = requests.get(
            url.format(serie=433, n=12), headers=headers, timeout=5
        ).json()
        selic = float(selic_data[-1]["valor"].replace(",", "."))
        taxas_ipca = [float(item["valor"].replace(",", ".")) / 100 for item in ipca_data]
        ipca = (prod(1 + taxa for taxa in taxas_ipca) - 1) * 100
        return round(selic, 2), round(ipca, 2), "Banco Central do Brasil"
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return FALLBACK_SELIC, FALLBACK_IPCA, "valores de contingência"


@lru_cache(maxsize=128)
def obter_fii(symbol: str) -> dict[str, Any]:
    """Consulta cotação, proventos em 12 meses e valor patrimonial no Yahoo."""
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="1y", auto_adjust=False)
    if history.empty:
        raise ValueError("O Yahoo Finance não retornou cotações para esse código.")

    preco = _safe_number(history["Close"].dropna().iloc[-1])
    if preco is None:
        raise ValueError("Não foi possível identificar a cotação atual.")

    dividendos = history.get("Dividends")
    proventos_12m = float(dividendos.fillna(0).sum()) if dividendos is not None else 0.0

    try:
        info = ticker.get_info()
    except Exception:
        info = {}
    nome = info.get("longName") or info.get("shortName") or symbol.removesuffix(".SA")
    return {
        "symbol": symbol.removesuffix(".SA"),
        "nome": nome,
        "preco": preco,
        "proventos_12m": proventos_12m,
    }


def metric_card(
    title: str,
    value_id: str,
    icon: str,
    color: str = "primary",
    card_id: str | None = None,
    subtitle_id: str | None = None,
):
    card_props = {"id": card_id} if card_id else {}
    content = [
        html.Div(
            [DashIconify(icon=icon, width=22), html.Span(title)],
            className=f"d-flex gap-2 align-items-center text-{color}",
        ),
        html.Div("—", id=value_id, className="metric-value mt-2"),
    ]
    if subtitle_id:
        content.append(
            html.Small(
                "—",
                id=subtitle_id,
                className="d-block text-muted metric-detail mt-1",
            )
        )
    return dbc.Card(
        dbc.CardBody(content),
        className="h-100 shadow-sm border-0 metric-card",
        **card_props,
    )


def slider_block(
    label: str,
    component_id: str,
    value: float,
    maximum: float = 20,
    minimum: float = 0,
    unit: str = "%",
):
    mark_step = 2
    marks = {
        i: f"{i:+d}{unit}" if minimum < 0 else f"{i}{unit}"
        for i in range(int(minimum), int(maximum) + 1, mark_step)
    }
    return html.Div(
        [
            html.Label(label, className="fw-semibold mb-2"),
            dcc.Slider(
                id=component_id,
                min=minimum,
                max=maximum,
                step=0.25,
                value=value,
                marks=marks,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ],
        className="mb-4",
    )


layout = dbc.Container(
    [
        dcc.Store(id="indices-carregados"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Div("ANÁLISE DE RENDA IMOBILIÁRIA", className="eyebrow"),
                                html.H1("Preço-teto de fundos imobiliários", className="display-5 fw-bold"),
                                html.P(
                                    "Compare a renda do FII com Selic ou IPCA, ajuste o "
                                    "prêmio de risco e descubra o preço máximo por cota.",
                                    className="lead text-secondary",
                                ),
                            ],
                            className="py-4",
                        )
                    ],
                    lg=8,
                ),
                dbc.Col(
                    dbc.Alert(
                        [
                            DashIconify(icon="solar:info-circle-linear", width=25),
                            html.Div(
                                [
                                    html.Strong("Premissas"),
                                    html.Div(
                                        "Proventos de 12 meses, reinvestimento integral e "
                                        f"IR de {ALIQUOTA_IR:.1f}% na Selic/IPCA."
                                    ),
                                ]
                            ),
                        ],
                        color="light",
                        className="d-flex gap-3 border align-items-start mt-lg-4",
                    ),
                    lg=4,
                ),
            ],
            align="center",
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
                                    id="fii-dropdown",
                                    options=FII_OPTIONS,
                                    value="HGLG11.SA",
                                    searchable=True,
                                    clearable=False,
                                    className="mb-4",
                                ),
                                html.Label("Referência de retorno", className="fw-semibold"),
                                dbc.RadioItems(
                                    id="modo-calculo",
                                    options=[
                                        {"label": " SELIC", "value": "selic"},
                                        {"label": " IPCA", "value": "ipca"},
                                    ],
                                    value="selic",
                                    inline=True,
                                    className="mb-4 mode-options",
                                ),
                                html.Div(
                                    slider_block("Taxa Selic anual", "taxa-selic", FALLBACK_SELIC),
                                    id="bloco-selic",
                                ),
                                html.Div(
                                    slider_block("IPCA acumulado em 12 meses", "taxa-ipca", FALLBACK_IPCA),
                                    id="bloco-ipca",
                                ),
                                slider_block(
                                    "Prêmio de risco (p.p.)",
                                    "premio-risco",
                                    0.0,
                                    maximum=15,
                                    minimum=-5,
                                    unit=" p.p.",
                                ),
                                dbc.Button(
                                    [DashIconify(icon="solar:calculator-linear", width=20), " Calcular"],
                                    id="calcular-button",
                                    color="primary",
                                    size="lg",
                                    className="w-100",
                                ),
                                html.Small(id="fonte-indices", className="d-block text-muted mt-3"),
                            ]
                        ),
                        className="shadow-sm border-0 config-card",
                    ),
                    lg=4,
                    className="mb-4",
                ),
                dbc.Col(
                    [
                        dbc.Alert(id="mensagem-erro", color="danger", is_open=False),
                        html.Div(id="nome-fii", className="text-secondary mb-2"),
                        dbc.ButtonGroup(
                            [
                                dbc.Button(
                                    [
                                        DashIconify(icon="solar:external-link-linear", width=18),
                                        " Ver no Clube FII",
                                    ],
                                    id="link-clubefii",
                                    href="https://www.clubefii.com.br/fiis/HGLG11",
                                    target="_blank",
                                    color="dark",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [
                                        DashIconify(icon="solar:external-link-linear", width=18),
                                        " Ver no Investidor10",
                                    ],
                                    id="link-investidor10",
                                    href="https://investidor10.com.br/fiis/HGLG11",
                                    target="_blank",
                                    color="primary",
                                    outline=True,
                                ),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    metric_card(
                                        "Cotação atual",
                                        "cotacao",
                                        "solar:tag-price-linear",
                                        card_id="card-cotacao",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(metric_card("Preço-teto", "preco-teto", "solar:target-linear", "success"), md=6),
                            ],
                            className="g-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    metric_card(
                                        "Dividend yield 12m",
                                        "dividend-yield",
                                        "solar:chart-2-linear",
                                        subtitle_id="dividend-yield-detalhe",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(
                                    metric_card(
                                        "Taxa líquida da alternativa",
                                        "taxa-liquida-alternativa",
                                        "solar:hand-money-linear",
                                        "warning",
                                        subtitle_id="taxa-liquida-detalhe",
                                    ),
                                    md=6,
                                ),
                            ],
                            className="g-3 mt-0",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    metric_card(
                                        "Taxa bruta equivalente do FII",
                                        "selic-equivalente-fii",
                                        "solar:scale-linear",
                                        "success",
                                        subtitle_id="selic-equivalente-fii-detalhe",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(
                                    metric_card(
                                        "Taxa bruta da referência usada",
                                        "selic-bruta-usada",
                                        "solar:chart-square-linear",
                                        "warning",
                                        subtitle_id="selic-bruta-usada-detalhe",
                                    ),
                                    md=6,
                                ),
                            ],
                            className="g-3 mt-0",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    metric_card(
                                        "Lucro estimado no FII",
                                        "lucro-fii",
                                        "solar:wallet-money-linear",
                                        "success",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(
                                    metric_card(
                                        "Lucro na alternativa",
                                        "lucro-referencia",
                                        "solar:banknote-2-linear",
                                        "warning",
                                    ),
                                    md=6,
                                ),
                            ],
                            className="g-3 mt-0",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Rendimento anual estimado", className="mb-1"),
                                    html.P(
                                        f"Simulação para {brl(INVESTIMENTO)}, com reinvestimento dos proventos.",
                                        className="text-muted",
                                    ),
                                    dcc.Loading(dcc.Graph(id="grafico-comparacao", config={"displayModeBar": False})),
                                ]
                            ),
                            className="shadow-sm border-0 mt-4",
                        ),
                        dbc.Alert(id="diagnostico", color="light", className="mt-4 border"),
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
    Output("taxa-selic", "value"),
    Output("taxa-ipca", "value"),
    Output("fonte-indices", "children"),
    Output("indices-carregados", "data"),
    Input("url", "pathname"),
    State("indices-carregados", "data"),
)
def carregar_indices(_pathname, carregado):
    if carregado:
        return no_update, no_update, no_update, no_update
    selic, ipca, fonte = obter_indices()
    return selic, ipca, f"Índices: {fonte}. Você pode ajustá-los em passos de 0,25 p.p.", True


@callback(
    Output("bloco-selic", "style"),
    Output("bloco-ipca", "style"),
    Input("modo-calculo", "value"),
)
def alternar_indice(modo):
    return ({}, {"display": "none"}) if modo == "selic" else ({"display": "none"}, {})


@callback(
    Output("link-clubefii", "href"),
    Output("link-investidor10", "href"),
    Input("fii-dropdown", "value"),
)
def atualizar_links_externos(symbol):
    ticker = (symbol or "").upper().removesuffix(".SA")
    return (
        f"https://www.clubefii.com.br/fiis/{ticker}",
        f"https://investidor10.com.br/fiis/{ticker}",
    )


@callback(
    Output("nome-fii", "children"),
    Output("cotacao", "children"),
    Output("card-cotacao", "className"),
    Output("preco-teto", "children"),
    Output("dividend-yield", "children"),
    Output("dividend-yield-detalhe", "children"),
    Output("taxa-liquida-alternativa", "children"),
    Output("taxa-liquida-detalhe", "children"),
    Output("selic-equivalente-fii", "children"),
    Output("selic-equivalente-fii-detalhe", "children"),
    Output("selic-bruta-usada", "children"),
    Output("selic-bruta-usada-detalhe", "children"),
    Output("lucro-fii", "children"),
    Output("lucro-referencia", "children"),
    Output("grafico-comparacao", "figure"),
    Output("diagnostico", "children"),
    Output("diagnostico", "color"),
    Output("mensagem-erro", "children"),
    Output("mensagem-erro", "is_open"),
    Input("calcular-button", "n_clicks"),
    State("fii-dropdown", "value"),
    State("modo-calculo", "value"),
    State("taxa-selic", "value"),
    State("taxa-ipca", "value"),
    State("premio-risco", "value"),
    prevent_initial_call=False,
)
def calcular(_clicks, symbol, modo, selic, ipca, premio):
    try:
        fii = obter_fii(symbol)
        indice = float(selic if modo == "selic" else ipca)
        premio = float(premio)
        fator_liquido_ir = 1 - ALIQUOTA_IR / 100
        taxa_referencia_liquida = indice * fator_liquido_ir
        taxa_alvo_fii = taxa_referencia_liquida + premio
        if taxa_alvo_fii <= 0:
            raise ValueError("A taxa-alvo precisa ser maior que zero.")

        preco = fii["preco"]
        proventos = fii["proventos_12m"]
        dy = proventos / preco * 100

        # Aproxima o reinvestimento dos proventos em parcelas mensais iguais.
        retorno_fii = ((1 + (dy / 100) / 12) ** 12 - 1) * 100
        taxa_alvo_mensal = (1 + taxa_alvo_fii / 100) ** (1 / 12) - 1
        preco_teto = proventos / (12 * taxa_alvo_mensal)

        # Gross-up do retorno efetivo atual do FII para uma aplicação tributada.
        selic_equivalente_fii = retorno_fii / fator_liquido_ir
        taxa_referencia_bruta = indice
        retorno_referencia = taxa_referencia_liquida
        finais = [
            INVESTIMENTO * (1 + retorno_fii / 100),
            INVESTIMENTO * (1 + retorno_referencia / 100),
        ]
        lucros = [valor_final - INVESTIMENTO for valor_final in finais]
        labels = [f"{fii['symbol']} (proventos reinvestidos)", f"{modo.upper()} líquido"]
        fig = go.Figure(
            go.Bar(
                x=labels,
                y=finais,
                text=[f"{brl(v)}<br>+{pct(r)}" for v, r in zip(finais, [retorno_fii, retorno_referencia])],
                textposition="outside",
                marker_color=["#136f63", "#d99b2b"],
            )
        )
        fig.update_layout(
            margin=dict(l=20, r=20, t=35, b=20),
            yaxis_title="Valor após 12 meses (R$)",
            yaxis_tickprefix="R$ ",
            yaxis_tickformat=",.0f",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )

        margem = (preco_teto / preco - 1) * 100
        abaixo = preco <= preco_teto
        diagnostico = (
            f"A cotação está {abs(margem):.1f}% "
            f"{'abaixo' if abaixo else 'acima'} do preço-teto. "
            f"{modo.upper()} líquido: {pct(taxa_referencia_liquida)}. "
            f"Prêmio de risco: {pp(premio)}. "
            f"Retorno mínimo exigido do FII: {pct(taxa_alvo_fii)}."
        )
        return (
            f"{fii['nome']} · {fii['symbol']} · proventos em 12m: {brl(proventos)} por cota",
            brl(preco),
            (
                "h-100 shadow-sm border-0 metric-card metric-card-success"
                if abaixo
                else "h-100 shadow-sm border-0 metric-card metric-card-danger"
            ),
            brl(preco_teto),
            pct(dy),
            (
                f"(1 + {pct(dy)} / 12)¹² - 1 = {pct(retorno_fii)} "
                f"→ valor final {brl(finais[0])}"
            ),
            pct(taxa_referencia_liquida),
            (
                f"{modo.upper()} {pct(indice)} × "
                f"(1 - IR {pct(ALIQUOTA_IR)}) = "
                f"{pct(taxa_referencia_liquida)} líquido; "
                f"+ prêmio {pp(premio)} = meta do FII {pct(taxa_alvo_fii)}"
            ),
            pct(selic_equivalente_fii),
            (
                f"Retorno efetivo do FII {pct(retorno_fii)} ÷ "
                f"(1 - IR {pct(ALIQUOTA_IR)})"
            ),
            pct(taxa_referencia_bruta),
            f"Taxa {modo.upper()} anual usada na simulação",
            brl(lucros[0]),
            brl(lucros[1]),
            fig,
            diagnostico,
            "success" if abaixo else "warning",
            "",
            False,
        )
    except Exception as exc:
        empty = go.Figure()
        empty.update_layout(
            annotations=[dict(text="Não foi possível carregar a simulação", showarrow=False)],
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return (
            "", "—", "h-100 shadow-sm border-0 metric-card", "—", "—",
            "—", "—", "—", "—", "—", "—", "—", "—", "—",
            empty, "", "light",
            f"Falha ao consultar o FII: {exc}. Tente novamente em alguns instantes.",
            True,
        )


dash.register_page(__name__, name="Calculadora", path="/", title="Preço-teto de FIIs")
