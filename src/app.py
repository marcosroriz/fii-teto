#!/usr/bin/env python
# coding: utf-8
"""Entrada da aplicação Dash de análise de fundos imobiliários."""

from __future__ import annotations

import os

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import Dash, Input, Output, State, _dash_renderer, callback, dcc, html
import plotly.graph_objects as go
import plotly.io as pio
from dotenv import load_dotenv
from werkzeug.middleware.profiler import ProfilerMiddleware

import tema

load_dotenv()
_dash_renderer._set_react_version("18.2.0")

pio.templates["fii_teto"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family=tema.FONTE_GRAFICOS, size=tema.FONTE_TAMANHO),
        colorway=["#136f63", "#d99b2b", "#274c77", "#8f5d5d"],
    )
)
pio.templates.default = "fii_teto"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Dash(
    "Preço-teto de FIIs",
    assets_folder=os.path.join(BASE_DIR, "assets"),
    pages_folder=os.path.join(BASE_DIR, "pages"),
    external_stylesheets=[
        dbc.themes.LUMEN,
        "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css",
    ],
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Preço-teto de FIIs",
)
server = app.server


def menu(vertical=True):
    return dbc.Nav(
        [
            dbc.NavLink(page["name"], href=page["relative_path"], active="exact")
            for page in dash.page_registry.values()
            if not page.get("hide_page", False)
        ],
        vertical=vertical,
        pills=True,
    )


header = dmc.Group(
    [
        dmc.Group(
            [
                dmc.Burger(id="burger-button", opened=False, hiddenFrom="sm"),
                html.Div("FT", className="brand-mark"),
                html.Div(
                    [html.Div("FII", className="brand-overline"), html.Div("Preço Teto", className="brand-title")]
                ),
            ],
            gap="sm",
        ),
        dmc.Group(menu(vertical=False), visibleFrom="sm"),
    ],
    justify="space-between",
    h="100%",
    px="lg",
)

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            dmc.AppShellHeader(header),
            dmc.AppShellNavbar(menu(vertical=True), id="navbar", p="md"),
            dmc.AppShellMain(
                [
                    dcc.Location(id="url", refresh="callback-nav"),
                    dash.page_container,
                    html.Footer(
                        "Ferramenta educacional. Não constitui recomendação de investimento.",
                        className="text-center text-muted py-4 small",
                    ),
                ]
            ),
        ],
        header={"height": 76},
        navbar={
            "width": 260,
            "breakpoint": "sm",
            "collapsed": {"desktop": True, "mobile": True},
        },
        padding="md",
        id="app-shell",
    )
)


@callback(
    Output("app-shell", "navbar"),
    Input("burger-button", "opened"),
    State("app-shell", "navbar"),
)
def toggle_navbar(opened, navbar):
    navbar["collapsed"] = {"mobile": not opened, "desktop": True}
    return navbar


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    port = int(os.getenv("PORT", "10000"))
    if os.getenv("PROFILE", "False").lower() in ("true", "1", "yes"):
        app.server.wsgi_app = ProfilerMiddleware(
            app.server.wsgi_app,
            sort_by=["cumtime"],
            restrictions=[50],
            profile_dir=os.getenv("PROFILE_DIR", "profile"),
        )
    app.run(host=host, debug=debug, port=port)
