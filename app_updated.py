import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

st.set_page_config(
    page_title="Edge-AI Water Quality Monitor",
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

st.title("💧 Edge-AI Water Quality Monitoring")
st.caption("AS7343 spectral analysis • pH/TDS estimates • ESP32 data workflow")

with st.sidebar:
    st.header("Data & model settings")
    uploaded = st.file_uploader("Upload sensor CSV", type=["csv"])
    contamination = st.slider(
        "Expected anomaly fraction",
        min_value=0.01, max_value=0.25, value=0.05, step=0.01,
        help="A model setting, not a measured contamination rate."
    )
    st.info(
        "For comparable spectra, keep LED position/brightness, cuvette geometry, "
        "sensor distance, and measurement procedure fixed."
    )

def demo_data(n=120, seed=7):
    """Synthetic data for interface testing only."""
    rng = np.random.default_rng(seed)
    baseline = np.array([
        16380, 17020, 16800, 16300, 17900, 17980, 16375, 17670, 17130,
        17530, 17940, 17990, 16220, 16530, 16300, 16830, 17935, 17990
    ], dtype=float)
    rows = []
    for i in range(n):
        values = baseline * (1 + rng.normal(0, 0.012, size=len(CHANNELS)))
        if i in {18, 49, 77, 101, 112}:
            values *= rng.choice([0.45, 1.65])
            values += rng.normal(0, baseline * 0.025, size=len(CHANNELS))
        row = {"sample_id": f"DEMO_{i+1:03d}", **dict(zip(CHANNELS, values))}
        rows.append(row)
    df_demo = pd.DataFrame(rows)
    df_demo["pH_estimated"] = np.nan
    df_demo["TDS_estimated_ppm"] = np.nan
    df_demo["data_source"] = "Synthetic demonstration data"
    return df_demo

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
        df.columns = [str(c).strip() for c in df.columns]
        df["data_source"] = "Uploaded sensor CSV"
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        st.stop()
else:
    st.warning(
        "No CSV uploaded. Showing synthetic demonstration data to test the dashboard. "
        "These are not real measurements and must not be used as project results."
    )
    df = demo_data()

missing = [c for c in CHANNELS if c not in df.columns]
if missing:
    st.error("CSV is missing required spectral columns: " + ", ".join(missing))
    st.markdown("Expected spectral columns:")
    st.code(",".join(["sample_id"] + CHANNELS))
    st.stop()

if "sample_id" not in df.columns:
    df.insert(0, "sample_id", [f"S{i+1:04d}" for i in range(len(df))])

# Optional fields from the combined ESP32 sketch.
OPTIONAL_NUMERIC = [
    "time_ms", "ph_adc", "ph_mV", "pH_estimated",
    "tds_adc", "tds_mV", "TDS_estimated_ppm"
]
for col in CHANNELS + OPTIONAL_NUMERIC:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(subset=CHANNELS).reset_index(drop=True)
if len(df) < 10:
    st.error(f"Only {len(df)} valid spectral rows found. Upload at least 10.")
    st.stop()

X = df[CHANNELS].to_numpy(dtype=float)
if not np.isfinite(X).all():
    st.error("Spectral columns contain non-finite values. Please clean the CSV.")
    st.stop()

# Unsupervised anomaly screening on spectral channels only.
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

anomaly_count = int((df["anomaly"] == "Anomaly").sum())
source_label = (
    "Synthetic demonstration data"
    if df["data_source"].astype(str).str.contains("Synthetic", case=False).any()
    else "Uploaded sensor data"
)

st.caption(f"Current source: **{source_label}**")

# Top-line project metrics.
m1, m2, m3, m4 = st.columns(4)
m1.metric("Valid readings", f"{len(df):,}")
m2.metric("Spectral channels", len(CHANNELS))
m3.metric("Flagged anomalies", f"{anomaly_count:,}")
m4.metric("Flagged fraction", f"{100 * anomaly_count / len(df):.1f}%")

has_ph = "pH_estimated" in df.columns and df["pH_estimated"].notna().any()
has_tds = "TDS_estimated_ppm" in df.columns and df["TDS_estimated_ppm"].notna().any()

st.subheader("Water sensor readings")
ph_col, tds_col, phv_col, tdsv_col = st.columns(4)

if has_ph:
    ph_values = df["pH_estimated"].dropna()
    ph_col.metric("Estimated pH — latest", f"{ph_values.iloc[-1]:.2f}")
    ph_col.caption(f"Observed range: {ph_values.min():.2f}–{ph_values.max():.2f}")
else:
    ph_col.metric("Estimated pH", "Not available")
    ph_col.caption("CSV has no numeric pH_estimated values.")

if has_tds:
    tds_values = df["TDS_estimated_ppm"].dropna()
    tds_col.metric("Estimated TDS — latest", f"{tds_values.iloc[-1]:.1f} ppm")
    tds_col.caption(f"Observed range: {tds_values.min():.1f}–{tds_values.max():.1f} ppm")
else:
    tds_col.metric("Estimated TDS", "Not available")
    tds_col.caption("CSV has no numeric TDS_estimated_ppm values.")

if "ph_mV" in df.columns and df["ph_mV"].notna().any():
    phv_col.metric("pH interface voltage", f"{df['ph_mV'].dropna().iloc[-1]:.1f} mV")
else:
    phv_col.metric("pH interface voltage", "Not available")

if "tds_mV" in df.columns and df["tds_mV"].notna().any():
    tdsv_col.metric("TDS interface voltage", f"{df['tds_mV'].dropna().iloc[-1]:.1f} mV")
else:
    tdsv_col.metric("TDS interface voltage", "Not available")

if has_ph or has_tds:
    st.warning(
        "pH and TDS are displayed as estimates from the ESP32 sketch. "
        "The pH slope is assumed and the TDS conversion must be validated against "
        "reference solutions. Do not treat these values as verified water-quality results."
    )

st.divider()
tab_overview, tab_water, tab_spectrum, tab_anomalies, tab_data = st.tabs(
    ["Overview", "pH & TDS", "Spectrum", "Anomaly review", "Dataset"]
)

with tab_overview:
    left, right = st.columns([1.4, 1])
    with left:
        fig = px.line(
            df, x="row_number", y="anomaly_score", color="anomaly",
            markers=True, title="Anomaly score by reading",
            labels={
                "row_number": "Reading number",
                "anomaly_score": "Anomaly score",
                "anomaly": "Model result",
            },
        )
        st.plotly_chart(fig, use_container_width=True)
    with right:
        counts = df["anomaly"].value_counts().rename_axis("Result").reset_index(name="Count")
        fig2 = px.pie(counts, names="Result", values="Count", title="Model flags")
        st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Isolation Forest is an unsupervised screening model. A flagged reading is unusual "
        "relative to this uploaded dataset; it does not prove contamination or unsafe water."
    )

with tab_water:
    st.subheader("pH and TDS trends")
    x_axis = "sample_id" if "sample_id" in df.columns else "row_number"

    if has_ph:
        ph_df = df.dropna(subset=["pH_estimated"]).copy()
        fig_ph = px.line(
            ph_df, x=x_axis, y="pH_estimated", markers=True,
            title="Estimated pH by reading",
            labels={"pH_estimated": "Estimated pH (demo)", x_axis: "Sample"},
        )
        st.plotly_chart(fig_ph, use_container_width=True)
    else:
        st.info("No numeric pH_estimated column was found in the uploaded CSV.")

    if has_tds:
        tds_df = df.dropna(subset=["TDS_estimated_ppm"]).copy()
        fig_tds = px.line(
            tds_df, x=x_axis, y="TDS_estimated_ppm", markers=True,
            title="Estimated TDS by reading",
            labels={"TDS_estimated_ppm": "Estimated TDS (ppm)", x_axis: "Sample"},
        )
        st.plotly_chart(fig_tds, use_container_width=True)
    else:
        st.info("No numeric TDS_estimated_ppm column was found in the uploaded CSV.")

    voltage_cols = [c for c in ["ph_mV", "tds_mV"] if c in df.columns and df[c].notna().any()]
    if voltage_cols:
        st.subheader("Raw analog interface voltages")
        voltage_df = df[[x_axis] + voltage_cols].melt(
            id_vars=[x_axis], var_name="Signal", value_name="Voltage (mV)"
        )
        fig_v = px.line(
            voltage_df, x=x_axis, y="Voltage (mV)", color="Signal", markers=True,
            title="Raw sensor interface voltage by reading",
        )
        st.plotly_chart(fig_v, use_container_width=True)

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
            labels={
                "channel_label": "Channel",
                "raw_count": "Raw sensor count",
                "sample_id": "Sample",
            },
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
        review_cols = ["sample_id", "anomaly_score"]
        review_cols += [c for c in ["pH_estimated", "TDS_estimated_ppm"] if c in df.columns]
        review_cols += CHANNELS
        st.dataframe(flagged[review_cols], use_container_width=True, hide_index=True)

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
    st.subheader("Sensor dataset and model results")
    display_cols = ["sample_id"]
    display_cols += [c for c in [
        "time_ms", "ph_adc", "ph_mV", "pH_estimated",
        "tds_adc", "tds_mV", "TDS_estimated_ppm"
    ] if c in df.columns]
    display_cols += CHANNELS + ["anomaly", "anomaly_score"]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    st.download_button(
        "Download sensor data + anomaly results",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="water_quality_dashboard_results.csv",
        mime="text/csv",
    )

with st.expander("CSV format and project limitations"):
    st.markdown(
        """
        The uploaded CSV must contain the 18 spectral channel columns:
        `FZ, FY, FXL, NIR, VIS1L, VIS1R, F2, F3, F4, F6, VIS2L, VIS2R, F1, F7, F8, F5, VIS3L, VIS3R`.

        The pH/TDS columns are optional. If present, this dashboard recognizes:
        `pH_estimated`, `TDS_estimated_ppm`, `ph_mV`, and `tds_mV`.

        - Synthetic demo data is not experimental evidence.
        - pH is an estimate because the current sketch uses an assumed slope.
        - TDS is an estimate until validated against a suitable reference solution.
        - An anomaly means “unusual within this dataset,” not “unsafe water.”
        - For stronger evaluation, collect known-normal baseline samples and independent test samples.
        """
    )

st.caption(
    "Prototype only • Not a certified water-quality instrument • "
    "Validate pH/TDS against reference measurements."
)
