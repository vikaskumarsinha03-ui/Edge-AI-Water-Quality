import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

st.set_page_config(
    page_title="Edge-AI Water Spectral Monitor",
    page_icon="💧",
    layout="wide",
)

CHANNELS = [
    "FZ", "FY", "FXL", "NIR", "VIS1L", "VIS1R", "F2", "F3", "F4",
    "F6", "VIS2L", "VIS2R", "F1", "F7", "F8", "F5", "VIS3L", "VIS3R"
]
CHANNEL_LABELS = {
    "FZ": "FZ (450 nm)", "FY": "FY (555 nm)", "FXL": "FXL (600 nm)",
    "NIR": "NIR (855 nm)", "VIS1L": "VIS Top-Left 1",
    "VIS1R": "VIS Bottom-Right 1", "F2": "F2 (425 nm)",
    "F3": "F3 (475 nm)", "F4": "F4 (515 nm)", "F6": "F6 (640 nm)",
    "VIS2L": "VIS Top-Left 2", "VIS2R": "VIS Bottom-Right 2",
    "F1": "F1 (405 nm)", "F7": "F7 (690 nm)", "F8": "F8 (745 nm)",
    "F5": "F5 (550 nm)", "VIS3L": "VIS Top-Left 3",
    "VIS3R": "VIS Bottom-Right 3",
}
REQUIRED = ["sample_id"] + CHANNELS

st.title("💧 Edge-AI Water Quality Monitoring")
st.caption("AS7343 spectral analysis • anomaly detection • ESP32 data workflow")

with st.sidebar:
    st.header("Data & model settings")
    uploaded = st.file_uploader("Upload spectral CSV", type=["csv"])
    contamination = st.slider(
        "Expected anomaly fraction",
        min_value=0.01, max_value=0.25, value=0.05, step=0.01,
        help="A starting assumption for Isolation Forest, not a measured error rate."
    )
    st.info(
        "Use repeated readings taken with the same sensor settings, LED position, "
        "cuvette geometry and sample procedure. Do not mix different setups in one baseline."
    )

def demo_data(n=120, seed=7):
    """Synthetic demonstration only; never presented as measured sensor data."""
    rng = np.random.default_rng(seed)
    baseline = np.array([
        16380, 17020, 16800, 16300, 17900, 17980, 16375, 17670, 17130,
        17530, 17940, 17990, 16220, 16530, 16300, 16830, 17935, 17990
    ], dtype=float)
    rows = []
    for i in range(n):
        values = baseline * (1 + rng.normal(0, 0.012, size=len(CHANNELS)))
        # Synthetic unusual spectra solely to demonstrate the UI/model pipeline.
        if i in {18, 49, 77, 101, 112}:
            values *= rng.choice([0.45, 1.65])
            values += rng.normal(0, baseline * 0.025, size=len(CHANNELS))
        row = {"sample_id": f"DEMO_{i+1:03d}", **dict(zip(CHANNELS, values))}
        rows.append(row)
    df = pd.DataFrame(rows)
    df["data_source"] = "SYNTHETIC DEMO — not real measurements"
    return df

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
        df["data_source"] = "Uploaded CSV"
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        st.stop()
else:
    st.warning(
        "No CSV uploaded. Showing **synthetic demonstration data** so you can test the dashboard. "
        "These values are not actual measurements and must not be used as project results."
    )
    df = demo_data()

# Normalize expected columns and validate.
df.columns = [str(c).strip() for c in df.columns]
missing = [c for c in CHANNELS if c not in df.columns]
if missing:
    st.error("CSV is missing these required spectral columns: " + ", ".join(missing))
    st.markdown("Expected columns: `sample_id` and the 18 channel names listed below.")
    st.code(",".join(["sample_id"] + CHANNELS))
    st.stop()

if "sample_id" not in df.columns:
    df.insert(0, "sample_id", [f"S{i+1:04d}" for i in range(len(df))])

for col in CHANNELS:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(subset=CHANNELS).reset_index(drop=True)
if len(df) < 10:
    st.error(f"Only {len(df)} valid rows found. Upload at least 10 valid spectral readings.")
    st.stop()

X = df[CHANNELS].to_numpy(dtype=float)
if not np.isfinite(X).all():
    st.error("Spectral columns contain non-finite values. Please clean the CSV.")
    st.stop()

# Model: scaling makes channel ranges comparable for this initial anomaly workflow.
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
model = IsolationForest(
    n_estimators=200,
    contamination=contamination,
    random_state=42,
)
pred = model.fit_predict(X_scaled)
df["anomaly"] = np.where(pred == -1, "Anomaly", "Normal")
df["anomaly_score"] = -model.score_samples(X_scaled)
df["row_number"] = np.arange(1, len(df) + 1)

normal_count = int((df["anomaly"] == "Normal").sum())
anomaly_count = int((df["anomaly"] == "Anomaly").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Valid readings", f"{len(df):,}")
m2.metric("Channels", len(CHANNELS))
m3.metric("Flagged anomalies", f"{anomaly_count:,}")
m4.metric("Flagged fraction", f"{100 * anomaly_count / len(df):.1f}%")

st.divider()
tab_overview, tab_spectrum, tab_anomalies, tab_data = st.tabs(
    ["Overview", "Spectrum", "Anomaly review", "Dataset"]
)

with tab_overview:
    left, right = st.columns([1.4, 1])
    with left:
        fig = px.line(
            df, x="row_number", y="anomaly_score", color="anomaly",
            markers=True, title="Anomaly score by reading",
            labels={"row_number": "Reading number", "anomaly_score": "Anomaly score", "anomaly": "Model result"},
        )
        st.plotly_chart(fig, use_container_width=True)
    with right:
        counts = df["anomaly"].value_counts().rename_axis("Result").reset_index(name="Count")
        fig2 = px.pie(counts, names="Result", values="Count", title="Model flags")
        st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Isolation Forest is an unsupervised screening model. A flagged reading is unusual relative "
        "to the uploaded dataset; it does not prove contamination or unsafe water."
    )

with tab_spectrum:
    selected_ids = st.multiselect(
        "Select readings to compare",
        options=df["sample_id"].astype(str).tolist(),
        default=df["sample_id"].astype(str).head(min(3, len(df))).tolist(),
    )
    if selected_ids:
        subset = df[df["sample_id"].astype(str).isin(selected_ids)]
        long_df = subset.melt(
            id_vars=["sample_id", "anomaly"],
            value_vars=CHANNELS,
            var_name="channel",
            value_name="raw_count",
        )
        long_df["channel_label"] = long_df["channel"].map(CHANNEL_LABELS)
        fig3 = px.line(
            long_df, x="channel_label", y="raw_count", color="sample_id",
            markers=True, title="Raw spectral-channel comparison",
            labels={"channel_label": "Channel", "raw_count": "Raw sensor count", "sample_id": "Sample"},
        )
        fig3.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Select one or more readings to plot.")

with tab_anomalies:
    st.subheader("Flagged readings")
    flagged = df[df["anomaly"] == "Anomaly"].sort_values("anomaly_score", ascending=False)
    if flagged.empty:
        st.success("No anomalies flagged at the selected model setting.")
    else:
        st.dataframe(
            flagged[["sample_id", "anomaly_score"] + CHANNELS],
            use_container_width=True,
            hide_index=True,
        )
    st.subheader("Inspect one reading")
    chosen = st.selectbox("Reading ID", df["sample_id"].astype(str).tolist())
    row = df[df["sample_id"].astype(str) == chosen].iloc[0]
    channel_df = pd.DataFrame({
        "Channel": CHANNELS,
        "Label": [CHANNEL_LABELS[c] for c in CHANNELS],
        "Raw count": [row[c] for c in CHANNELS],
    })
    fig4 = px.bar(channel_df, x="Channel", y="Raw count", title=f"Spectrum for {chosen}")
    st.plotly_chart(fig4, use_container_width=True)
    st.write(f"**Model result:** {row['anomaly']}  |  **Anomaly score:** {row['anomaly_score']:.5f}")

with tab_data:
    st.subheader("Validated input data")
    st.dataframe(df[["sample_id"] + CHANNELS + ["anomaly", "anomaly_score"]], use_container_width=True, hide_index=True)
    st.download_button(
        "Download results CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="spectral_anomaly_results.csv",
        mime="text/csv",
    )

with st.expander("CSV format and important limitations"):
    st.markdown(
        """
        Your CSV must contain one row per measurement and these columns:

        `sample_id,` plus all 18 spectral channel names: `FZ, FY, FXL, NIR, VIS1L, VIS1R, F2, F3, F4, F6, VIS2L, VIS2R, F1, F7, F8, F5, VIS3L, VIS3R`.

        - Collect multiple repeated readings under the same fixed setup.
        - Record sample identity and experimental conditions in extra columns if available.
        - Do not treat synthetic demo data as experimental evidence.
        - An anomaly means “different from this dataset,” not “unsafe water.”
        - For reliable deployment, train the baseline on known normal readings and evaluate against independent test samples.
        """
    )

st.caption("Prototype only • Not a certified water-quality instrument • Verify results with reference measurements.")
