# Edge-AI Based Water Quality Monitoring Using Multispectral Sensing
### Technical Design Review — Hardware, Optics, Data & ML Architecture

*Prepared as a critical engineering review. Datasheet claims below are verified against ams‑OSRAM AS7343 datasheet DS001046 (v6‑00, 2023‑Jun‑07).*

---

## 0. Quick Verdict on Your Assumptions

- **Your instinct about the white LED is correct — and important.** A single 6000–6500 K white LED is a **phosphor-converted LED**, not a continuous-spectrum source. It has a strong blue pump peak (~450 nm) and a broad but *uneven* phosphor hump (~550–650 nm), with very little energy beyond ~700 nm and essentially **nothing at 850 nm+**. Since the AS7343 has a dedicated NIR channel at 855 nm, a plain white LED will starve that channel of signal. This needs to be fixed (see below).
- The AS7343 is a real 14-channel part but **the channel set is not what a lot of tutorials assume** (many are copy-pasted from the older AS7341). Verified channel table is in Section 3.
- The AS7343 **cannot** measure pH, TDS, conductivity, or temperature directly. Any claim that it can must be removed from your report — this will be flagged by examiners immediately if left in.
- ESP32 as a controller is fine, but doing real "edge AI" inference on it is optional, not mandatory, for a working prototype — see Section on Edge AI.

---

## 1. Verified AS7343 Facts (from datasheet DS001046)

| Parameter | Value |
|---|---|
| Channel count | 14 optical channels (not counting the 6 "clear" sub-reads used internally for auto-SMUX cycling) |
| Spectral range | ~380 nm to ~1000 nm |
| Supply voltage (die) | 1.7–1.98 V, typ 1.8 V (breakout boards regulate this from 3.3 V/5 V for you) |
| Interface | I²C, 7-bit address **0x39** |
| Integrated LED driver | Yes — a current-sink LED driver pin (LDR) intended to drive an **external** LED, current programmable in steps (not enough current or thermal headroom to drive a 1 W LED directly — see Section 8) |
| Operating temp | −30 °C to 85 °C |
| Active current draw (die only) | ~210–280 µA | 
| Package | OLGA, 3.1 × 2 × 1 mm (this is why it's always sold on a breakout board, never bare) |

### Verified channel table (peak wavelength, FWHM)

| Channel | Peak λ (nm) | FWHM (nm) | Band |
|---|---|---|---|
| F1 | 405 | 30 | Violet |
| F2 | 425 | 22 | Violet-blue |
| FZ | 450 | 55 | Blue |
| F3 | 475 | 30 | Blue-cyan |
| F4 | 515 | 40 | Green |
| FY | 555 | 100 | Yellow-green (wide) |
| F5 | 550 | 35 | Green-yellow |
| FXL | 600 | 80 | Orange (wide) |
| F6 | 640 | 50 | Red |
| F7 | 690 | 55 | Deep red |
| F8 | 745 | 60 | Red / NIR edge |
| NIR | 855 | 54 | Near-infrared |
| CLEAR | Broadband | — | Unfiltered (6 sub-samples, TL/BR × 3 cycles, usually averaged) |
| FD (Flicker) | Broadband | — | 50/60 Hz ambient flicker detection, not useful for you |

This supersedes any AS7341-based channel list (F1=415, F8=680, NIR=910) you may have seen — that is a **different, older chip**. Use the table above for your CSV columns and report; do not mix the two.

---

## 2. Light Source — Direct Answers to Your 14 Sub-Questions

**1. Best illumination source:** A **dual-source approach**: (a) one high-CRI (Ra ≥ 90) white LED for the visible bands, and (b) one dedicated 850 nm NIR LED for the NIR channel. This is more reliable and far cheaper than halogen, and much more repeatable than a bank of 8+ single-wavelength LEDs.

**2. Which of your listed options:** → **"white + NIR LED"**, with the white LED upgraded from generic 6000–6500K to **high-CRI (Ra/CRI ≥ 90, ideally ≥ 95)**. Reasoning:
 - *Normal white LED alone*: rejected — negligible output past ~700 nm, so your NIR channel (855 nm) and F8 (745 nm) will read near-noise-floor. Also cheap white LEDs often have CRI 70–80 with dips in the cyan (~490 nm) and deep red (~650 nm) regions — exactly where several of your channels sample.
 - *High-CRI white LED alone*: better for visible bands, still weak at 850 nm+.
 - *Halogen*: has genuinely continuous blackbody-like spectrum into the NIR — optically the "most correct" choice — but brings real engineering headaches for a prototype: runs hot, needs a bulky driver, has slow warm-up/thermal drift, and is overkill for a college timeline. Not recommended.
 - *8 discrete single-wavelength LEDs (one per channel)*: gives you full control but multiplies your BOM, your driver electronics, your calibration burden, and your alignment/uniformity problems by 8×. Not realistic for a semester project.
 - **Recommended: white (high-CRI) + 850 nm NIR, switched sequentially** (see Q7 below).

**3. Wavelength range to cover:** ~400–700 nm from the white LED, plus ~850 nm from the NIR LED. You do not need to engineer illumination all the way to 1000 nm — the NIR channel's own FWHM (54 nm centered at 855 nm) means an 850 nm LED is a near-perfect match.

**4. Which channels are actually useful for water:**
 - **Highly useful:** F1–F4, FZ (405–515 nm, violet/blue/green) — sensitive to yellowness/tannins, algae pigment absorption (chlorophyll absorbs strongly ~430 nm and ~680 nm), dissolved organics.
 - **Useful:** F5, FY, FXL, F6 (550–640 nm) — general color/turbidity response, visible scattering.
 - **Useful, sometimes overlooked:** F7 (690 nm) — near chlorophyll's red absorption/fluorescence band, relevant if algae/eutrophication is one of your target classes.
 - **Important, don't skip:** F8 (745 nm) and NIR (855 nm) — turbidity and suspended-solids scattering is often *stronger and more linear* in NIR than in visible light, which is why NIR turbidity sensors (e.g. ISO 7027 standard) specifically use ~860–880 nm. This is genuinely one of your most valuable channels, not a throwaway.
 - **Marginal:** CLEAR (redundant with a weighted sum of the others), Flicker (not relevant — you're not sensing ambient light).

**5. How important is the NIR channel?** Very. It is arguably your single best turbidity indicator, and it's the internationally standardized wavelength region (ISO 7027 uses 860 nm ±30 nm and 780–900 nm for nephelometric turbidity). Don't treat it as an afterthought — treat it as a primary feature.

**6. Would an 850/860 nm NIR LED be useful?** Yes — **use one**. It's inexpensive (~₹20–80 for a 5 mm or SMD 850 nm IR LED in India), draws little power, and gives you a scientifically defensible turbidity channel that matches an actual water-quality standard (ISO 7027). This single component meaningfully strengthens your project's credibility.

**7. Should visible and NIR be measured separately?** **Yes — do them as two sequential exposures**, not simultaneously:
 1. Dark reading (all LEDs off) → subtract as baseline.
 2. White LED ON → capture all VIS channels (and ignore/discard NIR reading from this exposure, since ambient + white-LED bleed can contaminate it).
 3. White LED OFF, NIR LED ON → capture the NIR channel reading cleanly.
 This avoids the white LED's weak-but-nonzero tail past 800 nm from adding an unknown offset to your NIR reading, and avoids the NIR LED (invisible to the eye but present) from contaminating your visible-channel color measurements.

**8. Continuous or pulsed?** **Pulsed/strobed**, synchronized with the AS7343 integration window (turn LED on just before triggering a measurement, off afterward). Benefits: much lower average power (good for a USB/battery-powered prototype), less LED self-heating (heating shifts LED wavelength/output — a real source of drift), and it naturally supports the dark-frame subtraction in step 1 above.

**9. How should LED intensity be controlled?** With a **constant-current driver**, not a simple series resistor off a variable voltage. Keep the *drive current* fixed and identical across every single measurement session — this is what makes readings comparable at all. Do not use PWM dimming to "adjust brightness" between samples; if you must vary optical power, do it by adjusting the AS7343's own integration time/gain (software-side), not by changing LED current, because LED spectral shape shifts slightly with drive current.

**10. Constant-current driver recommendation:** For a 1 W-class LED (~300–350 mA), a simple **buck-based constant-current LED driver module** (e.g., an AL8860/AMC7135/XL4015-based module — widely sold in India as "1W/3W LED driver board 300mA" on Robu.in/Robocraze/Amazon.in) switched by an ESP32 GPIO through a small N-channel MOSFET (e.g., 2N7002/AO3400) is enough. For the 850 nm NIR LED (typically 20–100 mA), a MOSFET + fixed series resistor sized for that current is perfectly adequate — you don't need a dedicated CC driver for a single low-current NIR LED, just correct resistor sizing (R = (Vsupply − Vf_LED)/I_desired) and a decent heatsink path for the visible LED only.

**11. Diffuser:** A simple **PTFE (Teflon) diffuser disc or PTFE tape layer**, or frosted/ground glass, between the LED and the chamber. PTFE is cheap, chemically inert (good near water), and gives excellent, near-Lambertian diffusion — commonly used in real spectrometer integrating spheres/cuvette holders. A cheap alternative: a small piece of white translucent acrylic or a ping-pong-ball wall segment (a widely used hobbyist diffuser). Avoid anything colored/tinted — that will filter your spectrum before it even reaches the water.

**12. LED → water → sensor geometry/distance:** Keep it **short, fixed, and enclosed** — on the order of 10–25 mm from LED to the near wall of the water chamber, and 10–25 mm from the far wall to the sensor, inside a fully opaque housing (see Section 4). Exact distance matters less than **repeatability**: 3D-print or laser-cut a fixed jig so every sample sits at exactly the same position, every time.

**13. Transmission, reflection, or scattering?** **Transmission** (straight-through, LED and sensor on opposite sides of the water) is the most defensible, easiest-to-interpret, and easiest-to-build geometry for a semester project — it directly gives you an absorbance-like signal, which has decades of established water-quality literature behind it (color, turbidity via attenuation, organic content via UV-Vis absorption). 90° scattering (nephelometric geometry) is the *industry-standard* way to measure turbidity specifically (this is literally how ISO 7027 turbidimeters work), so it's a nice bonus if you have time, but transmission alone is sufficient and simpler for a first working prototype.

**14. Easiest/most reliable configuration for a college prototype:**
> **In-line transmission geometry**, white high-CRI LED + 850 nm NIR LED (pulsed, sequential), PTFE diffuser, constant-current drive, fixed-distance 3D-printed light-tight chamber, dark-frame subtracted, single fixed cuvette/vial position.

---

## 3. Optical Chamber Design

**Recommended geometry: (A) — sensor directly opposite the LED, water sample in between (straight-through transmission).**

Why (A) over the alternatives:
- **(A) Direct opposite (transmission)** — simplest to build, simplest to interpret (Beer–Lambert-style attenuation), most repeatable with a 3D-printed jig. **Recommended primary geometry.**
- **(B) 90° (scattering/nephelometric)** — technically the "correct" way to measure turbidity per ISO 7027, but harder to align, more sensitive to stray light leaks, and needs a black light-trap opposite the LED to absorb the unscattered beam so it doesn't overwhelm the 90° detector. Good **optional secondary measurement** if you have time, not a replacement for (A).
- **(C) Above/below** — mainly used for reflectance off a surface/sediment, not appropriate for a liquid sample volume; skip this for your use case.

**Chamber build recommendation (cheap, buildable with student tools):**
1. **Housing:** matte-black 3D-printed enclosure (PLA + black paint, or PETG — avoid glossy black which still specularly reflects) or a project box lined with black flock paper / black felt. Must fully exclude ambient light — this is the #1 practical failure mode in student optical projects.
2. **Sample holder:** a standard 10 mm or 12.5 mm square/round plastic cuvette (cheap, ~₹15–40 each on Amazon.in/lab suppliers) held in a snug 3D-printed slot so it drops into *exactly* the same position every time. Using a cuvette (rather than a random glass/jar) removes an entire axis of uncontrolled variability (glass thickness, shape).
3. **LED position:** fixed in a printed socket, LED axis perpendicular to the cuvette face, PTFE diffuser sandwiched immediately in front of the LED.
4. **Sensor position:** AS7343 module fixed directly opposite, module face perpendicular to the beam, at a small stand-off (a few mm) behind a small aperture (a 2–4 mm pinhole in an opaque partition) to reject stray/off-axis light and keep the effective optical path well-defined.
5. **Lid:** a snap/friction-fit opaque lid so the chamber can be closed light-tight for every measurement, opened only to swap the cuvette.

---

## 4. What AS7343 Can and Cannot Measure

**Realistically inferable (indirectly, via ML on spectral features):**
- **Color** — direct strength of the sensor; visible-channel ratios map well to perceived water color/tint.
- **Turbidity (proxy)** — via NIR/near-NIR attenuation or scattering, following the same physical principle as commercial nephelometers/turbidimeters (though a calibrated, certified NTU reading requires a proper nephelometer geometry and reference standards — your system gives a **relative, uncalibrated turbidity proxy** unless you invest in calibration against known NTU standards, e.g. formazin or commercial turbidity standards).
- **Suspended particles** — correlated with broadband attenuation/scattering across visible+NIR.
- **Dissolved organic matter / "yellowness" (CDOM-like effect)** — via blue-end absorption (short-wavelength attenuation is a classic optical signature of dissolved organics/tannins).
- **Algae/chlorophyll presence (qualitative)** — chlorophyll has known absorption features near 430 nm and 660–680 nm; F1–F3 and F6/F7 give you *some* sensitivity here, though a dedicated chlorophyll fluorometer would be far more specific.

**AS7343 CANNOT measure, and you must not claim it can:**
- **pH** — requires an ion-selective electrode or a colorimetric pH-indicator dye (which *could* theoretically be read optically, but that's a different, indirect chemical-indicator method, not a direct AS7343 capability).
- **TDS / conductivity** — requires a conductivity probe; TDS is an electrical property, not optical.
- **Temperature** — requires a thermistor/DS18B20 or similar; light sensors do not measure temperature (temperature does mildly affect *sensor dark current/drift*, which is a reason to log temperature — but not a way to measure the water's temperature).
- **Specific dissolved chemical identity/concentration** (e.g., nitrate ppm, heavy metals) — a 14-channel filter-based sensor does not have the spectral resolution or the UV range for chemical-specific absorption spectroscopy; this needs lab-grade instruments (UV-Vis spectrophotometer, ISE probes, or reagent-based colorimetric test kits).

**Recommendation:** add a **cheap DS18B20 temperature probe** (~₹40–80) as a genuinely useful, low-cost companion sensor — both because temperature affects the AS7343's dark counts (worth logging for drift correction) and because it lets your dashboard present at least one directly, unambiguously measured physical parameter alongside your optical inferences. If your scope/budget allows, a low-cost TDS module (~₹150–300) is a common, easy add-on that meaningfully strengthens the "water quality" story without much extra work — but this is optional, not required by the AS7343 itself.

---

## 5. Data Collection Plan

1. **Number of samples:** Aim for **≥ 8–12 distinct water conditions/classes** (e.g., tap water, filtered/RO water, muddy/turbid water at 2–3 concentrations, water with dissolved tea/organic tannin at 2–3 concentrations, water with a pinch of detergent, pond/lake water, water + food-color for a synthetic "colored contaminant" class). More classes and more within-class variety = a more defensible ML story.
2. **Readings per sample:** **≥ 15–20 independent readings per sample condition** — not 15 copies of the same cuvette insertion, but genuinely independent insertions (remove and reinsert the cuvette, or draw a fresh sub-sample) so you capture real-world repositioning noise, not just electronic noise.
3. **Repeated measurements:** Yes — take a **dark reading and 3–5 immediate repeat readings per insertion** (report the mean/median as the feature, and the std-dev as an optional data-quality/uncertainty feature).
4. **Preventing drift:** Let the LED/sensor warm up ~2–5 minutes before a session; keep drive current fixed (Section 2, Q9); re-run the dark + reference-standard calibration (Section 6) at the start of every session, and periodically (e.g., every 30 minutes) during long sessions; log ambient temperature.
5. **Normalizing for LED intensity:** Convert every raw channel reading into a **ratio relative to a reference standard** reading taken with the same LED/integration settings in the same session (see Section 6) — this cancels out session-to-session LED intensity drift.
6. **Dark reading:** **Yes, required**, every session (all LEDs off, lid closed) — subtract this per-channel offset from every subsequent reading before anything else.
7. **Reference/blank sample:** **Yes, required** — use distilled/RO water (optically closest to "pure") as your blank/reference for normalization, and ideally also a manufactured white/grey diffuse reflectance or transmission standard if you can obtain one (even a consistent PTFE/white-plastic chip used as a fixed reference target is a reasonable substitute for a college budget).
8. **Storage:** Log every raw channel value plus metadata (see CSV below) to **CSV via serial/Wi-Fi from the ESP32 to a laptop**, or directly to a microSD card as a fallback if Wi-Fi isn't convenient during fieldwork.
9. **Dataset CSV structure** (columns match the *verified* AS7343 channel names from Section 1 — do not use F1…F8 without also including FZ, FY, FXL, which are real distinct channels, not typos):

```
sample_id, sample_type, timestamp, temperature_C,
gain, integration_time_ms,
dark_F1, dark_F2, dark_FZ, dark_F3, dark_F4, dark_FY, dark_F5, dark_FXL, dark_F6, dark_F7, dark_F8, dark_NIR, dark_CLEAR,
vis_F1, vis_F2, vis_FZ, vis_F3, vis_F4, vis_FY, vis_F5, vis_FXL, vis_F6, vis_F7, vis_F8, vis_CLEAR,
nir_NIR,
reading_index, notes
```

Where `vis_*` are readings taken with the white LED on (Section 2, Q7) and `nir_NIR` is the NIR channel reading taken separately with the 850 nm LED on. Keep raw counts in this file; compute normalized/derived features in a later preprocessing step (Section 6) rather than baking transformations into the raw log — you'll thank yourself when you need to re-derive features differently later.

---

## 6. Calibration Procedure

1. **Dark measurement** — LEDs off, lid closed → per-channel dark offset `D_ch`.
2. **Reference measurement** — distilled/RO water (or a physical white/PTFE reference target) under identical LED + gain + integration-time settings → per-channel reference reading `R_ch`.
3. **Sample measurement** — the actual water sample under the same settings → raw reading `S_ch`.
4. **Recommended derived feature — transmittance-like ratio:**
   `T_ch = (S_ch − D_ch) / (R_ch − D_ch)`
5. **Recommended derived feature — absorbance-like value** (more linear with concentration for many optical properties, standard in colorimetry):
   `A_ch = −log10(T_ch)`
6. Use **both raw dark-subtracted counts** and the **derived ratio/absorbance features** as your ML feature set — let the model (or a quick feature-importance check) tell you which representation actually helps; don't assume in advance.
7. Repeat the dark + reference calibration **every session**, not once at project start — LED output and ambient conditions drift day to day.

---

## 7. Electronics: AS7343 → ESP32 → Computer

- **I²C:** AS7343 module SDA/SCL → ESP32 default I²C pins (commonly GPIO 21 = SDA, GPIO 22 = SCL on most ESP32 dev boards — confirm against your specific board's pinout diagram). Pull-up resistors (typically 4.7 kΩ) are usually already on the breakout module — verify by checking your specific 7Semi module's schematic/silkscreen; don't add a second set blindly, as doubled-up pull-ups can over-load the bus.
- **Voltage levels:** The AS7343 die itself runs at 1.8 V, but breakout modules (including the 7Semi one shown in your screenshot) include an onboard regulator and level shifting, so they accept **3.3 V** logic/power directly from the ESP32 — do **not** feed 5 V into the module unless its documentation explicitly says it's 5V-tolerant.
- **Power:** ESP32 (3.3 V logic, but often USB/5V powered with an onboard regulator) can directly power the sensor module. The **LED circuit should be powered/switched separately** through its own MOSFET + driver, not sourced directly from an ESP32 GPIO pin (GPIOs can only source a few mA — nowhere near enough for a 1 W LED).
- **LED driver & current limiting:** Visible LED → constant-current buck driver module (Section 2, Q10) enabled/disabled by an ESP32 GPIO through a logic-level N-channel MOSFET. NIR LED → simple series resistor sized for its target current, switched by a second MOSFET.
- **Grounding:** Use a **single common ground** between ESP32, sensor module, and LED driver circuit — star-ground back to one point if possible. Keep the LED driver's switching wires physically separated from the I²C SDA/SCL lines to avoid coupling switching noise into your data (a buck converter is a noise source; a filter sensor bus is noise-sensitive).
- **Possible noise issues:** (1) PWM/switching noise from the LED driver bleeding into I²C — mitigate with physical separation and a fully-off (not PWM-dimmed) LED during the actual ADC integration window; (2) ambient 50 Hz mains flicker — largely why the chip even has a flicker-detection channel, though you're sensing in a light-sealed box, so this should be minimal if your enclosure is genuinely light-tight; (3) ground loops if the LED driver and ESP32 use separate USB power sources — power everything from one common supply/ground where possible.
- **What the 7Semi module already includes vs. what you need externally:** The module itself gives you the AS7343 + regulator + level shifting + (check the specific 7Semi variant) possibly an onboard LED footprint. You will still need to add externally: your own high-CRI white LED + 850 nm NIR LED (the onboard LED, if present, is typically a small general-purpose white LED, not high-CRI and not NIR), the constant-current driver, MOSFET switches, diffuser, the physical chamber, and the ESP32 itself.

---

## 8. Software Architecture

```
ESP32 (firmware)
 ├─ I2C driver for AS7343 (init, gain/integration-time config, trigger reads)
 ├─ GPIO control for white-LED and NIR-LED switching (sequenced, pulsed)
 ├─ Dark-frame capture routine
 ├─ Packetize: {sample_id, timestamp, temp, gain, int_time, 13 raw channels ×2 exposures}
 └─ Transmit via Wi-Fi (HTTP POST / MQTT) or Serial-over-USB to host PC
        ↓
Python (host)
 ├─ Ingestion service (Flask/FastAPI endpoint, or pyserial listener) → append to CSV/SQLite
 ├─ Preprocessing: dark subtraction, ratio/absorbance feature computation, outlier rejection
 ├─ Feature store (per-sample feature vector)
 ├─ Trained scikit-learn model (joblib/pickle) → load once, predict on new samples
        ↓
Streamlit dashboard
 ├─ Live raw + derived spectral readings (numeric + bar/line chart)
 ├─ Prediction + class probability
 ├─ Historical log / trend view
 └─ Session calibration status (dark/reference age, warnings if stale)
```

Keep the ML training pipeline **offline** (a separate Jupyter/Python script you run periodically as your dataset grows), and have the Streamlit app only **load the trained model and run inference** — don't retrain live inside the dashboard.

---

## 9. Machine Learning

**Recommended primary model: Random Forest.** Reasoning for a small experimental dataset (likely tens to a few hundred samples, not thousands):
- **Random Forest** — robust to noisy/correlated spectral channels, needs little feature engineering, handles small-to-medium tabular data well, gives free feature importances (useful for your report — you can show *which channels matter*). **Primary recommendation.**
- **SVM (RBF kernel)** — a strong secondary choice, often competitive with RF on small, clean, moderate-dimensional tabular data; more sensitive to feature scaling (must standardize inputs first).
- **Logistic Regression** — good simple **baseline** to report against ("does the complex model actually beat a straight line?") and interpretable coefficients.
- **XGBoost** — can work well, but tends to need more data/tuning to beat Random Forest on a small dataset, and adds an extra dependency; reasonable as a secondary comparison, not a first choice.
- **Neural Network — not recommended as primary.** With a small hand-collected dataset (this is explicitly the situation you're in), a neural net has no meaningful advantage over RF/SVM and adds real risk of overfitting plus much less interpretability, which matters for a college evaluation. Mention it in your report only as "considered but not adopted, and explain why" — that's a stronger engineering statement than blindly using it.

**Preprocessing:** dark subtraction → ratio/absorbance feature computation (Section 6) → standardization (zero mean/unit variance) for SVM/LogReg (RF doesn't strictly need it, but it doesn't hurt to keep one consistent pipeline).

**Train/test split & cross-validation:** Use **stratified k-fold cross-validation** (k=5, stratified by class) for model selection/tuning, then a final held-out test set for the reported number.

**Avoiding data leakage — critical, and directly answering your question:** Because you take multiple repeated readings from the *same physical water sample/insertion*, those readings are highly correlated (near-duplicates). If some end up in train and some in test, your test accuracy will be **artificially inflated** — the model is effectively "recognizing" the same sample, not generalizing. **Fix: split by `sample_id` (the physical sample/batch), not by individual reading row.** All readings from one physical sample go entirely into either train or test, never split across both. This is called **group-aware splitting** — use `GroupKFold` / `StratifiedGroupKFold` in scikit-learn with `sample_id` as the group key, instead of plain `KFold`/`train_test_split`.

**Class imbalance:** If some water conditions are over-represented (e.g., many more "clean" than "contaminated" samples), use `class_weight='balanced'` (Random Forest/SVM/LogReg all support this directly) rather than naive oversampling on such a small dataset, to avoid manufacturing near-duplicate synthetic leakage.

**Evaluation metrics:** Report **accuracy** (overall correctness), but also **per-class precision, recall, and F1-score** (accuracy alone hides imbalanced-class failures), plus a **confusion matrix** (shows exactly which water types get confused with which — genuinely informative for a water-quality classifier, e.g. "turbid vs. algae-heavy get confused" is a useful, reportable finding).

---

## 10. Edge AI — What Actually Runs Where

Being called "Edge-AI" does **not** require the ESP32 to run the trained model itself, and for a first working prototype it's genuinely reasonable not to:

- **ESP32 should do:** sensor acquisition, LED sequencing/timing, dark-frame subtraction (simple arithmetic — cheap), and packaging/transmission of the reading. This is legitimate "edge preprocessing," and is enough to honestly justify "Edge-AI" in your title if you frame it as *edge-based data acquisition and preprocessing feeding a trained ML model*.
- **ESP32 could (optional stretch goal) do:** run a small trained model directly on-device using **TensorFlow Lite Micro** or a hand-exported Random-Forest-as-if/else-tree (RF trees export very cheaply to plain C code — this is actually easier to run on an ESP32 than a neural net, and Random Forest is what we already recommended for accuracy reasons). This is a nice "true edge inference" upgrade if you have time left, and a genuinely defensible thing to claim once done.
- **Realistic baseline architecture for a college prototype:** ESP32 handles acquisition + LED control + dark subtraction + transmission; the trained model runs on the host PC/laptop (feeding the Streamlit dashboard). Call this "edge-assisted" honestly in your report rather than overclaiming full on-device inference unless you actually implement the TFLite-Micro/exported-tree stretch goal.

---

## 11. Dashboard (Streamlit) Recommendations

Include:
- Live raw + dark-subtracted spectral readings (numeric table + bar chart across the 13 channels).
- Prediction + class probability/confidence (e.g., "Turbid — 82% confidence").
- Historical readings/trend view, filterable by sample ID or session.
- Calibration status indicator (age of last dark/reference calibration; warn if stale).
- Sample metadata entry (sample name/location/notes) at capture time.

**Do not** display language like "safe to drink" or make potability claims — your system has not been validated against a certified reference method (e.g., a lab turbidimeter, official water-quality testing) or regulatory standards (e.g., BIS/WHO drinking water limits). Frame outputs as **relative/comparative water-quality classification** (e.g., "clear / turbid / high-organic-content, relative to calibrated reference"), not as a certified potability verdict.

---

## 12. System Architecture (Revised)

```
Water Sample (fixed cuvette position)
        ↓
Controlled Illumination (high-CRI white LED + 850nm NIR LED, pulsed, sequential)
        ↓
AS7343 Multispectral Sensor (transmission geometry, light-tight chamber)
        ↓
ESP32 (I2C acquisition, LED sequencing, dark-frame subtraction, packaging)
        ↓
Wi-Fi / Serial Transmission
        ↓
Python host: preprocessing (ratio/absorbance features), feature store (CSV/SQLite)
        ↓
Trained Random Forest / SVM model (offline-trained, loaded for inference)
        ↓
Water-Quality Classification + Confidence
        ↓
Streamlit Dashboard (live readings, prediction, history, calibration status)
```

This differs from your original diagram mainly by making the **illumination step explicit and dual-source**, and by clarifying that **ESP32 does acquisition/preprocessing, while the trained model itself runs on the host** unless you pursue the on-device stretch goal in Section 10.

---

## 13. Hardware Shopping List (BOM)

> **Note on prices/links:** I verified the AS7343 module's category and one live Bengaluru-store listing from your own screenshot (7Semi AS7343 module, Robocraze, ₹1,594). For the remaining components I could not verify a specific, currently-live purchase link without risking giving you a stale or incorrect one — per your instruction not to invent links, I'm giving you **exact specifications to search for** on Robu.in, Robocraze, Amazon.in, or a local electronics market (e.g., SP Road, Bengaluru), with **approximate Indian price ranges** based on typical market rates. Please verify current price/stock yourself before purchasing.

| # | Component | Spec | Why | Approx. price (INR) |
|---|---|---|---|---|
| 1 | AS7343 module | 7Semi 14-channel breakout, I²C | Core sensor | ~₹1,594 (verified: Robocraze, Bengaluru) |
| 2 | ESP32 dev board | ESP32-WROOM-32 (DevKit-C or similar) | MCU + Wi-Fi | ₹350–500 |
| 3 | High-CRI white LED | 1 W, CRI ≥ 90 (ideally ≥95), 5000–6500 K, on a small MCPCB star | Broad, even visible-spectrum illumination | ₹80–200 |
| 4 | NIR LED | 850 nm (or 860 nm), 5 mm through-hole or SMD, ~20–50 mA rated | ISO-7027-style turbidity channel excitation | ₹20–80 |
| 5 | Constant-current LED driver | Buck-based CC driver module, ~300 mA output (for the 1 W visible LED) | Stable, repeatable optical output | ₹60–150 |
| 6 | N-channel logic-level MOSFETs ×2 | e.g., AO3400/2N7002-class, logic-level gate | ESP32-GPIO-controlled LED switching | ₹10–30 each |
| 7 | Series resistor (for NIR LED) | Value calculated from (Vsupply−Vf)/I_target, ≥ 1/4W | Current limiting for NIR LED | ₹5 |
| 8 | Diffuser material | PTFE tape/sheet or frosted acrylic disc | Even illumination, no hotspots | ₹50–150 |
| 9 | Sample cuvettes | 10 mm/12.5 mm plastic disposable cuvettes, pack | Fixed, repeatable optical path length | ₹150–400/pack |
| 10 | Chamber housing | 3D-printed black PLA/PETG enclosure, or matte-black project box + black flock lining | Light-tight, fixed geometry | ₹200–600 (print) or ₹150–300 (box) |
| 11 | DS18B20 temperature probe | Waterproof digital temp sensor | Log sample/ambient temp for drift correction and dashboard | ₹80–150 |
| 12 | Wires/connectors | Jumper wires, JST connectors, breadboard/perfboard | Assembly | ₹100–200 |
| 13 | Reference standard | PTFE white reflectance chip, or consistently use distilled/RO water as blank | Calibration reference (Section 6) | ₹0 (distilled water) to ₹300+ (commercial standard) |
| 14 | (Optional) TDS module | Analog TDS sensor + probe | Adds one genuinely-measured non-optical parameter | ₹150–300 |
| 15 | Power supply | 5V/2A USB supply, common ground | Power for ESP32 + LED driver | ₹150–250 |

**Estimated total (core system, without optional TDS):** roughly **₹3,000–4,000**, dominated by the AS7343 module itself.

---

## FINAL RECOMMENDATIONS

**A) RECOMMENDED FINAL HARDWARE**
7Semi AS7343 module + ESP32-WROOM-32 + high-CRI (≥90 CRI) 1W white LED + 850 nm NIR LED + constant-current driver + MOSFET switching + PTFE diffuser + 3D-printed light-tight transmission chamber with fixed cuvette slot + DS18B20 temperature logger.

**B) RECOMMENDED OPTICAL GEOMETRY**
Straight-through **transmission** geometry (LED — water cuvette — sensor, in line), inside a fully opaque, light-sealed enclosure, with a small aperture in front of the sensor to reject stray light.

**C) RECOMMENDED LED**
Dual source: **high-CRI (≥90, ideally ≥95) white LED** for visible channels + **850 nm NIR LED** for the NIR channel, both constant-current driven, pulsed sequentially (visible exposure, then NIR exposure, with a dark frame per session).

**D) RECOMMENDED DATA-COLLECTION PROCEDURE**
≥8–12 distinct water conditions, ≥15–20 independent readings each, dark + reference calibration every session, dark-subtracted + ratio/absorbance derived features, all logged with a `sample_id` that groups repeated readings from the same physical sample.

**E) RECOMMENDED ML PIPELINE**
Random Forest as primary model (SVM and Logistic Regression as comparison baselines), stratified **group-aware** cross-validation split by `sample_id` (never split individual repeated readings across train/test), `class_weight='balanced'` for imbalance, report per-class precision/recall/F1 and a confusion matrix — not just accuracy.

**F) THINGS YOU MUST NOT CLAIM IN YOUR PROJECT**
- That the AS7343 directly measures pH, TDS, conductivity, or temperature.
- That your turbidity/organic-content outputs are certified NTU/regulatory values, unless independently calibrated against a certified reference instrument.
- That the system determines water is "safe to drink" or meets any potability standard (BIS/WHO) — this requires validated, regulator-recognized testing methods you are not implementing.
- That the ESP32 performs full on-device ML inference, unless you actually implement and test that (Section 10) — otherwise, describe the architecture honestly as edge-acquisition + host-side inference.

**G) NEXT 10 STEPS**
1. Verify your specific 7Semi AS7343 module's onboard LED (if any) and I²C pull-up presence from its schematic before wiring.
2. Order the high-CRI white LED and 850 nm NIR LED; do not proceed with the plain 6000–6500K LED alone.
3. Design and 3D-print (or build from a project box) the light-tight transmission chamber with a fixed cuvette slot.
4. Wire ESP32 ↔ AS7343 (I²C) and ESP32 ↔ MOSFETs ↔ LED driver/NIR LED.
5. Write firmware: I²C init, gain/integration-time config, LED sequencing (dark → visible → NIR), packet formatting, Wi-Fi/serial transmission.
6. Run and validate the dark-subtraction + reference-normalization calibration routine end-to-end before collecting any real dataset.
7. Collect the structured dataset per Section 5/9 (distinct water conditions × repeated independent readings, grouped by `sample_id`).
8. Build the offline preprocessing + feature-engineering script (ratio/absorbance features) and the Random Forest training/evaluation notebook with group-aware CV.
9. Build the Streamlit dashboard: live readings, prediction + confidence, history, calibration-status indicator.
10. Write up findings honestly, including the "must not claim" list above, feature-importance results, and confusion-matrix-based error analysis as your discussion/limitations section — examiners generally reward honest limitations sections in a water-quality/health-adjacent project.

---

*Uncertainties flagged for your own verification before finals submission: (1) exact onboard components of your specific 7Semi module revision — check its schematic; (2) live prices/stock for LED/driver components — verify at time of purchase; (3) your ESP32 board's exact default I²C GPIO pins — confirm against your specific board's pinout diagram, as this varies slightly between ESP32 dev board vendors.*
