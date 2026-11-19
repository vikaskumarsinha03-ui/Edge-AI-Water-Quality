import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import joblib
import csv
import io
import serial
from streamlit_autorefresh import st_autorefresh
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


MODEL_PATH = "water_sample_classifier_4class.joblib"

@st.cache_resource
def load_sample_classifier(model_path):
    """Load the trained sample-category model if it is present."""
    return joblib.load(model_path)


st.title("💧 Edge-AI Water Quality Monitoring")
st.caption("AS7343 spectral analysis • pH/TDS estimates • ESP32 data workflow")

with st.sidebar:
    st.header("Data & model settings")
    source_mode = st.radio(
        "Data source",
        ["Upload CSV", "Live ESP32"],
        index=0,
        help="Choose CSV upload for saved readings or Live ESP32 for USB serial readings."
    )
    uploaded = None
    serial_port = "COM3"
    serial_baud = 115200

    if source_mode == "Upload CSV":
        uploaded = st.file_uploader("Upload sensor CSV", type=["csv"])
    else:
        serial_port = st.text_input("ESP32 serial port", value="COM3")
        serial_baud = st.selectbox("Baud rate", [115200, 9600], index=0)
        connect_col, disconnect_col = st.columns(2)
        with connect_col:
            if st.button("Connect", use_container_width=True):
                try:
                    old_conn = st.session_state.get("esp32_serial")
                    if old_conn is not None:
                        try:
                            old_conn.close()
                        except Exception:
                            pass
                    st.session_state.esp32_serial = serial.Serial(
                        serial_port.strip(), int(serial_baud), timeout=0.05
                    )
                    st.session_state.esp32_header = None
                    st.session_state.esp32_rows = []
                    st.session_state.esp32_line_buffer = ""
                    st.session_state.esp32_connected_port = serial_port.strip()
                    st.success(f"Connected to {serial_port.strip()}. Waiting for CSV header and readings…")
                except Exception as exc:
                    st.error(f"Could not open {serial_port}: {exc}")
        with disconnect_col:
            if st.button("Disconnect", use_container_width=True):
                conn = st.session_state.get("esp32_serial")
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                st.session_state.esp32_serial = None
                st.session_state.esp32_header = None
                st.session_state.esp32_rows = []
                st.session_state.esp32_line_buffer = ""
                st.info("ESP32 disconnected.")

        if st.session_state.get("esp32_serial") is not None:
            st.caption(f"Connected port: {st.session_state.get('esp32_connected_port', serial_port)}")
            st_autorefresh(interval=1000, key="esp32_live_refresh")

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

def read_live_serial_rows():
    """Read available ESP32 CSV lines without blocking the Streamlit page."""
    conn = st.session_state.get("esp32_serial")
    if conn is None:
        return

    if "esp32_rows" not in st.session_state:
        st.session_state.esp32_rows = []
    if "esp32_header" not in st.session_state:
        st.session_state.esp32_header = None
    if "esp32_line_buffer" not in st.session_state:
        st.session_state.esp32_line_buffer = ""

    try:
        waiting = conn.in_waiting
        if waiting:
            chunk = conn.read(waiting).decode("utf-8", errors="ignore")
            st.session_state.esp32_line_buffer += chunk

        while "\n" in st.session_state.esp32_line_buffer:
            line, st.session_state.esp32_line_buffer = (
                st.session_state.esp32_line_buffer.split("\n", 1)
            )
            line = line.strip().replace("\r", "")
            if not line:
                continue

            # The ESP32 may print boot messages before the CSV header.
            fields = next(csv.reader([line]))
            if "sample_id" in fields and "FZ" in fields and "VIS3R" in fields:
                st.session_state.esp32_header = [item.strip() for item in fields]
                continue

            header = st.session_state.get("esp32_header")
            if not header or len(fields) != len(header):
                continue

            row = dict(zip(header, fields))
            if not str(row.get("sample_id", "")).strip().isdigit():
                # Ignore malformed lines; normal sample IDs are numeric.
                continue

            # Convert sensor fields to numeric values where possible.
            clean_row = {}
            for key, value in row.items():
                try:
                    clean_row[key] = float(value)
                except (TypeError, ValueError):
                    clean_row[key] = value

            clean_row["sample_id"] = int(clean_row["sample_id"])
            clean_row["data_source"] = "Live ESP32 serial"
            st.session_state.esp32_rows.append(clean_row)

            # Keep a bounded recent window so the dashboard stays responsive.
            st.session_state.esp32_rows = st.session_state.esp32_rows[-500:]
    except Exception as exc:
        st.warning(f"Serial read issue: {exc}")


if source_mode == "Live ESP32":
    read_live_serial_rows()
    live_rows = st.session_state.get("esp32_rows", [])
    if not live_rows:
        st.info(
            "Live mode is selected. Click Connect in the sidebar, keep the ESP32 "
            "connected by USB, and wait for the CSV header and readings. Close Arduino "
            "Serial Monitor first so it releases the COM port."
        )
        st.stop()
    df = pd.DataFrame(live_rows)
    df["data_source"] = "Live ESP32 serial"
elif uploaded is not None:
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
minimum_rows = 1 if source_mode == "Live ESP32" else 10
if len(df) < minimum_rows:
    st.error(f"Only {len(df)} valid spectral rows found. Need at least {minimum_rows}.")
    st.stop()

X = df[CHANNELS].to_numpy(dtype=float)
if not np.isfinite(X).all():
    st.error("Spectral columns contain non-finite values. Please clean the CSV.")
    st.stop()

# Supervised sample-category prediction (only for uploaded real sensor data).
# This predicts similarity to the collected categories; it does not assess water safety.
classifier_available = False
if source_mode == "Live ESP32" or (
    uploaded is not None and not df["data_source"].astype(str).str.contains(
        "Synthetic", case=False
    ).any()
):
    try:
        classifier_bundle = load_sample_classifier(MODEL_PATH)
        sample_classifier = classifier_bundle["model"]
        model_channels = classifier_bundle.get("spectral_columns", CHANNELS)

        missing_model_channels = [c for c in model_channels if c not in df.columns]
        if missing_model_channels:
            st.warning(
                "Sample classifier could not run because these spectral channels are missing: "
                + ", ".join(missing_model_channels)
            )
        else:
            model_X = df[model_channels].to_numpy(dtype=float)
            spectral_labels = sample_classifier.predict(model_X)
            df["spectral_model_prediction"] = spectral_labels
            predicted_labels = pd.Series(spectral_labels, index=df.index, dtype="object")

            if hasattr(sample_classifier, "predict_proba"):
                probabilities = sample_classifier.predict_proba(model_X)
                df["spectral_model_confidence_pct"] = probabilities.max(axis=1) * 100
            else:
                df["spectral_model_confidence_pct"] = np.nan

            # Hybrid decision rule for this prototype:
            # 1) Preserve spectral detections for Soil and Tea.
            # 2) For other samples, use TDS_estimated_ppm:
            #       < 220 ppm  -> RO water
            #       >= 220 ppm -> Tap water
            # This is an experimental heuristic, not a validated water-safety test.
            tds_col = "TDS_estimated_ppm"
            if tds_col in df.columns:
                tds_values = pd.to_numeric(df[tds_col], errors="coerce")

                for pos, idx in enumerate(df.index):
                    label = str(spectral_labels[pos]).strip().lower()
                    label_key = label.replace(" ", "_").replace("-", "_")
                    tds_value = tds_values.loc[idx]

                    if "soil" in label_key:
                        predicted_labels.loc[idx] = "soil_water"
                    elif "tea" in label_key:
                        predicted_labels.loc[idx] = "tea_water"
                    elif pd.notna(tds_value) and tds_value < 220:
                        predicted_labels.loc[idx] = "ro_water"
                    elif pd.notna(tds_value) and tds_value >= 220:
                        predicted_labels.loc[idx] = "tap_water"
                    else:
                        # Missing/invalid TDS: do not invent an RO/Tap result.
                        predicted_labels.loc[idx] = spectral_labels[pos]

                df["tds_rule_applied"] = tds_values.notna()
                if not tds_values.notna().any():
                    st.warning(
                        "'TDS_estimated_ppm' exists, but has no numeric readings. "
                        "The 220 ppm rule cannot run until Arduino sends numeric TDS values."
                    )
            else:
                df["tds_rule_applied"] = False
                st.warning(
                    "TDS rule NOT applied: 'TDS_estimated_ppm' is missing. "
                    "The Arduino CSV header and each data row must include this column "
                    "in the matching position."
                )

            df["predicted_sample_type"] = predicted_labels

            # The displayed confidence remains the spectral model confidence;
            # it is not a probability for the hybrid TDS rule.
            df["prediction_confidence_pct"] = df["spectral_model_confidence_pct"]
            classifier_available = True
    except FileNotFoundError:
        st.warning(
            f"Trained classifier file not found: {MODEL_PATH}. "
            "Place it in the same folder as app.py to enable sample-category predictions."
        )
    except Exception as exc:
        st.warning(f"Could not load or run the sample classifier: {exc}")

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
if df["data_source"].astype(str).str.contains("Synthetic", case=False).any():
    source_label = "Synthetic demonstration data"
elif df["data_source"].astype(str).str.contains("Live ESP32", case=False).any():
    source_label = "Live ESP32 serial readings"
else:
    source_label = "Uploaded sensor data"

st.caption(f"Current source: **{source_label}**")

if source_mode == "Live ESP32":
    st.caption("Live serial mode displays the most recent readings received over USB.")
    st.download_button(
        "Download received live readings as CSV",
        data=df.drop(columns=["data_source"], errors="ignore").to_csv(index=False).encode("utf-8"),
        file_name="live_esp32_readings.csv",
        mime="text/csv",
    )

if classifier_available:
    st.subheader("AI sample-category prediction")
    st.caption(
        "Hybrid demo prediction: spectral model for sample patterns plus an experimental TDS threshold "
        "(below 220 ppm → RO; 220 ppm or above → Tap, except spectral Soil/Tea detections). "
        "TDS values are estimates and this rule is not validated; predictions do not determine drinking-water safety."
    )
    latest_prediction = df.iloc[-1]
    p1, p2 = st.columns(2)
    p1.metric("Latest predicted category", str(latest_prediction["predicted_sample_type"]).replace("_", " ").title())
    confidence = latest_prediction.get("prediction_confidence_pct", np.nan)
    if pd.notna(confidence):
        p2.metric("Model confidence (latest reading)", f"{confidence:.1f}%")
    prediction_counts = (
        df["predicted_sample_type"].value_counts()
        .rename_axis("Predicted category").reset_index(name="Readings")
    )
    fig_predictions = px.bar(
        prediction_counts, x="Predicted category", y="Readings",
        title="Predicted categories in uploaded readings"
    )
    st.plotly_chart(fig_predictions, use_container_width=True)
    st.dataframe(
        df[["sample_id", "predicted_sample_type", "prediction_confidence_pct"]].tail(10),
        use_container_width=True, hide_index=True
    )
elif source_mode == "Upload CSV" and uploaded is None:
    st.info(
        "Upload a real ESP32 sensor CSV or select Live ESP32 to run the trained "
        "sample-category classifier. Synthetic demo readings are not classified."
    )

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
    display_cols += CHANNELS
    display_cols += [c for c in ["predicted_sample_type", "prediction_confidence_pct"] if c in df.columns]
    display_cols += ["anomaly", "anomaly_score"]
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
