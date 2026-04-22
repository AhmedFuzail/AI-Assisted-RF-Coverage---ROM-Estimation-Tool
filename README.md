# 📡 RF Coverage & ROM Estimation Tool

A Streamlit-based web application to quickly estimate **RF coverage** and **Rough Order of Magnitude (ROM)** for Private 5G and Neutral Host deployments.

---

## 🚀 Live App
👉 https://your-app-name.streamlit.app

---

## 🎯 Overview

This tool helps RF engineers, solution architects, and leadership teams:
- Estimate coverage for indoor environments
- Predict infrastructure requirements (DOTs, radios)
- Generate quick ROM (cost estimates)
- Reduce manual RF design effort

---

## ⚙️ Key Features

- 📊 Data-driven RF coverage estimation
- 🏢 Supports multiple building types & clutter profiles
- 📐 Ceiling height & construction-based modeling
- ⚡ Instant ROM calculation (DOTs per sqft)
- 🔁 Fast iteration vs traditional iBwave workflows

---

## 🧠 How It Works

1. User selects:
   - Building type
   - Construction type
   - Clutter profile
   - Ceiling height

2. Tool applies:
   - Predefined RF loss models
   - Coverage assumptions
   - DOT density logic

3. Outputs:
   - Estimated coverage range
   - Number of DOTs required
   - ROM estimation

---

## 🛠️ Tech Stack

- Python
- :contentReference[oaicite:0]{index=0}
- Pandas / NumPy
- Plotly (if used)

---

## ▶️ Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
streamlit run app.py