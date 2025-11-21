# dply_interact_app.py

import copy
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.graph_objects as go


# --------------------------------
# Initialize Dash with Bootstrap
# --------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX],
)
server = app.server


# -----------------------------
# 1. DATA: compartments & flows
# -----------------------------
NODES = [
    "FEED_PURCHASED",
    "FEED_HOMEGROWN",
    "ANIMALS",
    "FEEDER_PIGS_IMP",
    "FERT_PURCHASED",
    "MANURE_STORAGE",
    "SOIL_AVAILABLE",
    "SOIL_STABLE",
    "CROPS",
    "PIG_EXPORTS",
    "GRAIN_EXPORTS",
    "ENVIRONMENT",
    "CARCASSES",
]

NODE_IDX = {name: i for i, name in enumerate(NODES)}

BASE_FLOWS_N = {
    "F1": 4800,
    "F2": 800,
    "F3": 300,
    "F4": 0,
    "F5": 2400,
    "F6": 2400,
    "F7": 900,
    "F8": 1900,
    "F9": 200,
    "F10": 300,
    "F11": 1300,
    "F12": 300,
    "F13": 300,
    "F14": 0,
    "F15": 800,
    "F16": 500,
    "F17": 200,
    "F18": 50,
    "F19": 100,
    "F20": 50,
}

LINKS = [
    ("FEED_PURCHASED", "ANIMALS", "F1"),
    ("FEED_HOMEGROWN", "ANIMALS", "F2"),
    ("FEEDER_PIGS_IMP", "ANIMALS", "F3"),
    ("FERT_PURCHASED", "SOIL_AVAILABLE", "F4"),
    ("ANIMALS", "PIG_EXPORTS", "F5"),
    ("ANIMALS", "MANURE_STORAGE", "F6"),
    ("ANIMALS", "ENVIRONMENT", "F7"),
    ("MANURE_STORAGE", "SOIL_AVAILABLE", "F8"),
    ("MANURE_STORAGE", "SOIL_STABLE", "F9"),
    ("MANURE_STORAGE", "ENVIRONMENT", "F10"),
    ("SOIL_AVAILABLE", "CROPS", "F11"),
    ("SOIL_AVAILABLE", "ENVIRONMENT", "F12"),
    ("SOIL_AVAILABLE", "SOIL_STABLE", "F13"),
    ("SOIL_STABLE", "SOIL_AVAILABLE", "F14"),
    ("CROPS", "FEED_HOMEGROWN", "F15"),
    ("CROPS", "GRAIN_EXPORTS", "F16"),
    ("ANIMALS", "CARCASSES", "F17"),
    ("CARCASSES", "SOIL_AVAILABLE", "F18"),
    ("CARCASSES", "PIG_EXPORTS", "F19"),
    ("CARCASSES", "ENVIRONMENT", "F20"),
]


# -------------------------------------------------
# 2. METRICS
# -------------------------------------------------
def compute_circularity_metrics_N(flows):
    input_N = flows["F1"] + flows["F3"] + flows["F4"]
    pig_exports = flows["F5"] + flows["F19"]
    grain_exports = flows["F16"]

    circular_N = pig_exports + grain_exports
    accessible_N = 50.0

    env_loss = flows["F7"] + flows["F10"] + flows["F12"] + flows["F20"]
    locked_stable = 500.0

    lost_N = env_loss + locked_stable

    return {
        "input_N": input_N,
        "circular_N": circular_N,
        "accessible_N": accessible_N,
        "lost_N": lost_N,
        "env_loss": env_loss,
        "locked_stable": locked_stable,
    }


# -----------------------------------------
# 3. FIGURES
# -----------------------------------------
def make_sankey_figure(flows):
    sources = [NODE_IDX[src] for (src, tgt, fid) in LINKS]
    targets = [NODE_IDX[tgt] for (src, tgt, fid) in LINKS]
    values = [flows[fid] for (src, tgt, fid) in LINKS]

    fig = go.Figure(
        data=[go.Sankey(
            arrangement="snap",
            node=dict(
                pad=15,
                thickness=20,
                line=dict(width=0.5),
                label=NODES,
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
            ),
        )]
    )

    fig.update_layout(
        title_text="Nitrogen Flows (kg N/year)",
        width=900,
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
    )

    return fig


def make_circularity_bar_figure(metrics):
    input_N = metrics["input_N"]
    circular = metrics["circular_N"] / input_N * 100
    accessible = metrics["accessible_N"] / input_N * 100
    lost = metrics["lost_N"] / input_N * 100

    fig = go.Figure(
        data=[go.Bar(
            x=["Circular", "Accessible", "Lost"],
            y=[circular, accessible, lost],
            text=[f"{circular:.1f}%", f"{accessible:.1f}%", f"{lost:.1f}%"],
            textposition="auto",
        )]
    )

    fig.update_layout(
        title="N Circularity Breakdown",
        width=400,
        height=400,
        margin=dict(l=60, r=20, t=60, b=40),
    )

    return fig


# ---------------------------
# 4. LAYOUT
# ---------------------------
baseline_metrics = compute_circularity_metrics_N(BASE_FLOWS_N)

app.layout = html.Div([
    html.H2("Toy Pig Nutrient Circularity DST – Nitrogen Demo"),

    html.Div([
        html.Label("Reduce housing N losses (F7) by (%)"),
        dcc.Slider(
            id="housing-reduction",
            min=0,
            max=50,
            step=1,
            value=5,
            marks={0: "0%", 10: "10%", 25: "25%", 50: "50%"},
        ),
    ], style={"maxWidth": "500px", "marginBottom": "20px"}),

    html.Div(style={"display": "flex", "gap": "40px"}, children=[
        html.Div(style={"flex": "2"}, children=[
            dcc.Graph(
                id="sankey-graph",
                figure=make_sankey_figure(BASE_FLOWS_N),
                style={"height": "520px"}
            )
        ]),
        html.Div(style={"flex": "1"}, children=[
            dcc.Graph(
                id="circularity-bar",
                figure=make_circularity_bar_figure(baseline_metrics)
            ),
            html.H4("Key Numbers (kg N/yr)"),
            html.Ul(id="metrics-list", children=[
                html.Li(f"External N input = {baseline_metrics['input_N']:.0f}"),
                html.Li(f"Circular = {baseline_metrics['circular_N']:.0f}"),
                html.Li(f"Accessible = {baseline_metrics['accessible_N']:.0f}"),
                html.Li(f"Lost = {baseline_metrics['lost_N']:.0f}"),
            ])
        ]),
    ])
])


# ---------------------------
# 5. CALLBACK
# ---------------------------
@app.callback(
    [
        Output("sankey-graph", "figure"),
        Output("circularity-bar", "figure"),
        Output("metrics-list", "children"),
    ],
    Input("housing-reduction", "value"),
)
def update_scenario(housing_reduction_percent):
    flows = copy.deepcopy(BASE_FLOWS_N)

    reduction = housing_reduction_percent / 100.0
    saved = flows["F7"] * reduction

    flows["F7"] *= (1 - reduction)
    flows["F6"] += saved

    metrics = compute_circularity_metrics_N(flows)

    metrics_children = [
        html.Li(f"External N input = {metrics['input_N']:.0f}"),
        html.Li(f"Circular = {metrics['circular_N']:.0f}"),
        html.Li(f"Accessible = {metrics['accessible_N']:.0f}"),
        html.Li(f"Lost = {metrics['lost_N']:.0f}"),
        html.Li(f"Housing loss (F7) = {flows['F7']:.0f}"),
    ]

    return (
        make_sankey_figure(flows),
        make_circularity_bar_figure(metrics),
        metrics_children,
    )


if __name__ == "__main__":
    app.run(debug=True)
