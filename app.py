# app.py
import dash
from dash import dcc, html
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


# -------------------------------------------------
# 2. METRICS: Circular / Accessible / Lost for N
# -------------------------------------------------

def compute_circularity_metrics_N(flows: dict) -> dict:
    """
    Simple demonstration of circular vs accessible vs lost for N.

    - Input_N: external N into the farm (purchased feed, feeder pigs, fert).
    - Circular_N: N leaving as useful products (pigs + grain + carcass exports).
    - Accessible_N: residual N in plant-available soil pool (toy: fixed 50).
    - Lost_N: env losses + stable soil buildup (treated as 'locked').
    """
    # External input N (to farm)
    input_N = flows["F1"] + flows["F3"] + flows["F4"]  # purchased feed + feeder pigs + fert

    # Useful exports (products)
    pig_exports = flows["F5"] + flows["F19"]  # market pigs + carcass-derived products
    grain_exports = flows["F16"]
    circular_N = pig_exports + grain_exports  # 2400 + 100 + 500 = 3000

    # Accessible residual N in SOIL_AVAILABLE (toy assumption)
    accessible_N = 50.0

    # Environmental losses
    env_loss = flows["F7"] + flows["F10"] + flows["F12"] + flows["F20"]
    # Long-term stable soil buildup (toy assumption: net +500)
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


metrics_N = compute_circularity_metrics_N(BASE_FLOWS_N)


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
        title_text="Nitrogen Flows (kg N/year) – Baseline Grow-Finish Farm",
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
        title="Nitrogen Circularity Breakdown (Baseline)",
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

app.layout = html.Div(
    style={"fontFamily": "Arial, sans-serif", "margin": "20px"},
    children=[
        html.H2("Toy Pig Nutrient Circularity DST – Nitrogen Demo"),

        html.P(
            "This simplified demo uses a single nutrient (N) and a single baseline scenario "
            "to illustrate how matrix-based flows can be visualized and summarized in a Dash app."
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
                            style={"height": "520px"},  # roughly match figure height
                        )
                    ],
                ),
                html.Div(
                    style={"flex": "1", "maxWidth": "450px"},
                    children=[
                        dcc.Graph(
                            id="circularity-bar",
                            figure=make_circularity_bar_figure(metrics_N),
                            style={"height": "420px"},
                        ),
                        html.H4("Key Numbers (N, kg/year):"),
                        html.Ul([
                            html.Li(f"External N input = {metrics_N['input_N']:.0f} kg N/yr"),
                            html.Li(f"Circular (products) = {metrics_N['circular_N']:.0f} kg N/yr"),
                            html.Li(f"Accessible (soil available) = {metrics_N['accessible_N']:.0f} kg N/yr"),
                            html.Li(f"Lost (env + locked) = {metrics_N['lost_N']:.0f} kg N/yr"),
                            html.Li(f"Total environmental N loss = {metrics_N['env_loss']:.0f} kg N/yr"),
                            html.Li(f"Net stable soil N gain = {metrics_N['locked_stable']:.0f} kg N/yr"),
                        ]),
                    ],
                ),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True)
