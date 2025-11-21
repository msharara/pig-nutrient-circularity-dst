# app.py
import copy

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# -----------------------------
# 1. DATA: compartments & flows
# -----------------------------

# Compartment (node) names (C1–C13)
NODES = [
    "FEED_PURCHASED",   # C1
    "FEED_HOMEGROWN",   # C2
    "ANIMALS",          # C3
    "FEEDER_PIGS_IMP",  # C4
    "FERT_PURCHASED",   # C5
    "MANURE_STORAGE",   # C6
    "SOIL_AVAILABLE",   # C7
    "SOIL_STABLE",      # C8
    "CROPS",            # C9
    "PIG_EXPORTS",      # C10
    "GRAIN_EXPORTS",    # C11
    "ENVIRONMENT",      # C12
    "CARCASSES",        # C13
]

# Map node name → index (for Sankey)
NODE_IDX = {name: i for i, name in enumerate(NODES)}

# Baseline N flows F1–F20 in kg N/year
BASE_FLOWS_N = {
    "F1":  4800,  # FEED_PURCHASED → ANIMALS
    "F2":  800,   # FEED_HOME_TO_PIGS → ANIMALS
    "F3":  300,   # FEEDER_PIGS_TO_PIGS → ANIMALS
    "F4":  0,     # FERT_TO_SOIL → SOIL_AVAILABLE
    "F5":  2400,  # PIG_TO_EXPORT → PIG_EXPORTS
    "F6":  2400,  # PIG_EXCRETION → MANURE_STORAGE
    "F7":  900,   # HOUSING_LOSS → ENVIRONMENT
    "F8":  1900,  # MANURE_TO_SOIL_AV → SOIL_AVAILABLE
    "F9":  200,   # MANURE_TO_SOIL_ST → SOIL_STABLE
    "F10": 300,   # STORAGE_LOSS → ENVIRONMENT
    "F11": 1300,  # CROP_UPTAKE → CROPS
    "F12": 300,   # FIELD_LOSS → ENVIRONMENT
    "F13": 300,   # IMMOBILIZATION → SOIL_STABLE
    "F14": 0,     # MINERALIZATION → SOIL_AVAILABLE
    "F15": 800,   # CROPS_TO_FEED → FEED_HOMEGROWN
    "F16": 500,   # CROPS_TO_EXPORT → GRAIN_EXPORTS
    "F17": 200,   # MORTALITY → CARCASSES
    "F18": 50,    # CARCASS_TO_SOIL → SOIL_AVAILABLE
    "F19": 100,   # CARCASS_TO_PIG_EXP → PIG_EXPORTS
    "F20": 50,    # CARCASS_TO_ENV → ENVIRONMENT
}

# Define links (source, target, flow_id)
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

# -----------------------------
# 1a. DERIVED PARTITION FRACTIONS (for cascading)
# -----------------------------

# Partition of manure excretion F6 into F8/F9/F10 (from baseline)
_storage_out_total = BASE_FLOWS_N["F8"] + BASE_FLOWS_N["F9"] + BASE_FLOWS_N["F10"]  # 1900+200+300=2400
P_F8 = BASE_FLOWS_N["F8"] / _storage_out_total  # fraction to soil available
P_F9 = BASE_FLOWS_N["F9"] / _storage_out_total  # fraction to soil stable
P_F10 = BASE_FLOWS_N["F10"] / _storage_out_total  # fraction to env from storage

# Partition of soil-available outflow (F11+F12+F13) (from baseline)
_soil_out_total = BASE_FLOWS_N["F11"] + BASE_FLOWS_N["F12"] + BASE_FLOWS_N["F13"]  # 1300+300+300=1900
P_F11 = BASE_FLOWS_N["F11"] / _soil_out_total   # crop uptake
P_F12 = BASE_FLOWS_N["F12"] / _soil_out_total   # field loss
P_F13 = BASE_FLOWS_N["F13"] / _soil_out_total   # immobilization

# Partition of crop N to feed vs export (from baseline)
_crop_in_baseline = BASE_FLOWS_N["F11"]  # 1300
P_F15 = BASE_FLOWS_N["F15"] / _crop_in_baseline  # to feed
P_F16 = BASE_FLOWS_N["F16"] / _crop_in_baseline  # to grain export

ACCESSIBLE_TARGET = 50.0  # kg N/yr in plant-available soil at end of year


# -------------------------------------------------
# 2. METRICS: Circular / Accessible / Lost for N
# -------------------------------------------------

def compute_circularity_metrics_N(flows: dict) -> dict:
    """
    Compute circular vs accessible vs lost for N using the current flows.

    - Input_N: external N into the farm (purchased feed, feeder pigs, fert).
    - Circular_N: N leaving as useful products (pigs + grain + carcass exports).
    - Accessible_N: residual N in plant-available soil pool (C7).
    - Lost_N: env losses (all env flows) + net stable soil gain.
    """
    # External input N (to farm)
    input_N = flows["F1"] + flows["F3"] + flows["F4"]  # purchased feed + feeder pigs + fert

    # Useful exports (products)
    pig_exports = flows["F5"] + flows["F19"]  # market pigs + carcass-derived products
    grain_exports = flows["F16"]
    circular_N = pig_exports + grain_exports

    # Soil-available compartment C7: inflow
    C7_in = flows["F4"] + flows["F8"] + flows["F14"] + flows["F18"]
    accessible_N = min(ACCESSIBLE_TARGET, C7_in)

    # Environmental losses (all flows to ENVIRONMENT)
    env_loss = flows["F7"] + flows["F10"] + flows["F12"] + flows["F20"]

    # Net stable soil gain = inflow (F9+F13) - outflow (F14)
    locked_stable = flows["F9"] + flows["F13"] - flows["F14"]

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
# 3. FIGURES: Sankey + bar chart for N
# -----------------------------------------

def make_sankey_figure(flows: dict) -> go.Figure:
    """Build a Plotly Sankey figure from NODES and LINKS using N flows."""
    sources = [NODE_IDX[src] for (src, tgt, fid) in LINKS]
    targets = [NODE_IDX[tgt] for (src, tgt, fid) in LINKS]
    values = [flows[fid] for (src, tgt, fid) in LINKS]

    fig = go.Figure(data=[go.Sankey(
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
        )
    )])

    fig.update_layout(
        title_text="Nitrogen Flows (kg N/year) – Baseline / Scenario",
        font=dict(size=12),
        autosize=False,
        width=900,
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def make_circularity_bar_figure(metrics: dict) -> go.Figure:
    """Bar chart of Circular vs Accessible vs Lost fractions of N input."""
    input_N = metrics["input_N"]
    circular = metrics["circular_N"] / input_N * 100
    accessible = metrics["accessible_N"] / input_N * 100
    lost = metrics["lost_N"] / input_N * 100

    categories = ["Circular (products)", "Accessible (soil available)", "Lost (env + locked)"]
    values = [circular, accessible, lost]

    fig = go.Figure(
        data=[go.Bar(
            x=categories,
            y=values,
            text=[f"{v:.1f}%" for v in values],
            textposition="auto",
        )]
    )
    fig.update_yaxes(title="Percent of external N input", range=[0, 100])
    fig.update_layout(
        title="Nitrogen Circularity Breakdown",
        margin=dict(l=60, r=20, t=60, b=40),
        autosize=False,
        width=400,
        height=400,
    )
    return fig


# ---------------------------
# 4. DASH APP LAYOUT
# ---------------------------

app = dash.Dash(__name__)

baseline_metrics = compute_circularity_metrics_N(BASE_FLOWS_N)

app.layout = html.Div(
    style={"fontFamily": "Arial, sans-serif", "margin": "20px"},
    children=[
        html.H2("Toy Pig Nutrient Circularity DST – Nitrogen Demo"),

        html.P(
            "Baseline grow–finish farm N budget using a matrix-based representation. "
            "Adjust housing N losses and see how flows and circularity metrics respond "
            "with simple cascading behavior."
        ),

        html.Div(
            style={"marginBottom": "20px", "maxWidth": "500px"},
            children=[
                html.Label("Reduce housing N losses (F7) by (%)"),
                dcc.Slider(
                    id="housing-reduction",
                    min=0,
                    max=50,
                    step=1,
                    value=5,
                    marks={0: "0%", 5: "5%", 10: "10%", 25: "25%", 50: "50%"},
                ),
            ],
        ),

        html.Div(
            style={"display": "flex", "gap": "40px"},
            children=[
                html.Div(
                    style={"flex": "2", "minWidth": "600px"},
                    children=[
                        dcc.Graph(
                            id="sankey-graph",
                            figure=make_sankey_figure(BASE_FLOWS_N),
                            style={"height": "520px"},
                        )
                    ],
                ),
                html.Div(
                    style={"flex": "1", "maxWidth": "450px"},
                    children=[
                        dcc.Graph(
                            id="circularity-bar",
                            figure=make_circularity_bar_figure(baseline_metrics),
                            style={"height": "420px"},
                        ),
                        html.H4("Key Numbers (N, kg/year):"),
                        html.Ul(
                            id="metrics-list",
                            children=[
                                html.Li(f"External N input = {baseline_metrics['input_N']:.0f} kg N/yr"),
                                html.Li(f"Circular (products) = {baseline_metrics['circular_N']:.0f} kg N/yr"),
                                html.Li(f"Accessible (soil available) = {baseline_metrics['accessible_N']:.0f} kg N/yr"),
                                html.Li(f"Lost (env + locked) = {baseline_metrics['lost_N']:.0f} kg N/yr"),
                                html.Li(f"Total environmental N loss = {baseline_metrics['env_loss']:.0f} kg N/yr"),
                                html.Li(f"Net stable soil N gain = {baseline_metrics['locked_stable']:.0f} kg N/yr"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ---------------------------
# 5. CALLBACK: apply cascading intervention
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
    """
    Adjust housing N loss (F7) by a given % reduction, with cascading effects:

    - N saved from housing emissions goes to excretion (F6).
    - Excretion (F6) is repartitioned to F8/F9/F10 using baseline fractions.
    - Soil available inflow (C7) is repartitioned to F11/F12/F13 using baseline fractions
      while keeping a target accessible pool (ACCESSIBLE_TARGET).
    - Crop N (F11) is repartitioned to F15 (feed) and F16 (export) with baseline fractions.

    External inputs (F1, F3, F4) and pig product flows (F5, F19) remain fixed.
    """
    flows = copy.deepcopy(BASE_FLOWS_N)

    # 1) Reduce housing loss F7 and send saved N to excretion F6
    reduction_factor = housing_reduction_percent / 100.0
    baseline_F7 = BASE_FLOWS_N["F7"]
    baseline_F6 = BASE_FLOWS_N["F6"]

    new_F7 = baseline_F7 * (1 - reduction_factor)
    delta = baseline_F7 - new_F7  # N saved from housing emissions

    flows["F7"] = new_F7
    flows["F6"] = baseline_F6 + delta

    # 2) Repartition F6 → F8, F9, F10 using baseline fractions
    flows["F8"] = flows["F6"] * P_F8
    flows["F9"] = flows["F6"] * P_F9
    flows["F10"] = flows["F6"] * P_F10

    # 3) Soil-available pool (C7) inflow and outflow
    C7_in = flows["F4"] + flows["F8"] + flows["F14"] + flows["F18"]
    accessible_N = min(ACCESSIBLE_TARGET, C7_in)
    outflow_from_C7 = max(C7_in - accessible_N, 0.0)

    flows["F11"] = outflow_from_C7 * P_F11
    flows["F12"] = outflow_from_C7 * P_F12
    flows["F13"] = outflow_from_C7 * P_F13

    # 4) Crops: repartition F11 into F15 (feed) and F16 (export)
    flows["F15"] = flows["F11"] * P_F15
    flows["F16"] = flows["F11"] * P_F16

    # Recompute metrics with new flows
    metrics = compute_circularity_metrics_N(flows)

    sankey_fig = make_sankey_figure(flows)
    bar_fig = make_circularity_bar_figure(metrics)

    metrics_children = [
        html.Li(f"External N input = {metrics['input_N']:.0f} kg N/yr"),
        html.Li(f"Circular (products) = {metrics['circular_N']:.0f} kg N/yr"),
        html.Li(f"Accessible (soil available) = {metrics['accessible_N']:.0f} kg N/yr"),
        html.Li(f"Lost (env + locked) = {metrics['lost_N']:.0f} kg N/yr"),
        html.Li(f"Total environmental N loss = {metrics['env_loss']:.0f} kg N/yr"),
        html.Li(f"Net stable soil N gain = {metrics['locked_stable']:.0f} kg N/yr"),
        html.Li(f"Housing N loss (F7) = {flows['F7']:.0f} kg N/yr"),
        html.Li(f"Excreted N to storage (F6) = {flows['F6']:.0f} kg N/yr"),
    ]

    return sankey_fig, bar_fig, metrics_children


if __name__ == "__main__":
    app.run(debug=True)
