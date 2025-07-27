import streamlit as st
import pandas as pd

# -------------------------
# Hard‑coded file paths
# -------------------------
CPV_FILE = r"C:\Users\Asus\Downloads\Cost_Conv Location Wise - March to May 27th 2025 - Countrywise Avg Cpv - Infeed + Instream.csv"
CPS_FILE = r"C:\Users\Asus\Downloads\Cost_Conv Location Wise - March to May 27th 2025 - Cost_Conv Location Wise - March to May 27th 2025.csv"

INR_TO_USD = 1 / 85

# -------------------------
# Caching loaders
# -------------------------
@st.cache_data
def load_cpvs(filepath: str) -> dict[str, float]:
    raw = pd.read_csv(filepath, header=None)
    first = pd.to_numeric(raw.iloc[0, 1], errors='coerce')
    data = raw.iloc[1:, [0,1]] if pd.isna(first) else raw.iloc[:, [0,1]]
    data.columns = ["Country", "CPV_INR"]
    data["Country"] = data["Country"].str.strip().str.casefold()
    data["CPV_INR"] = pd.to_numeric(data["CPV_INR"], errors='coerce').fillna(0)
    return dict(zip(data["Country"], data["CPV_INR"]))

@st.cache_data
def load_cps(filepath: str) -> dict[str, float]:
    raw = pd.read_csv(filepath, header=None)
    first = pd.to_numeric(raw.iloc[0, 1], errors='coerce')
    data = raw.iloc[1:, [0,1]] if pd.isna(first) else raw.iloc[:, [0,1]]
    data.columns = ["Country", "CPS_INR"]
    data["Country"] = data["Country"].str.strip().str.casefold()
    data["CPS_INR"] = pd.to_numeric(data["CPS_INR"], errors='coerce').fillna(0)
    data.loc[data["CPS_INR"] == 0, "CPS_INR"] = 10.0
    return dict(zip(data["Country"], data["CPS_INR"]))

# -------------------------
# Cost calculator
# -------------------------
def calculate_cost(total_inr: float, markup_pct: float):
    client = total_inr * (1 + markup_pct/100)
    return (
        round(total_inr,2),
        round(total_inr * INR_TO_USD,2),
        round(client,2),
        round(client * INR_TO_USD,2),
    )

# -------------------------
# App start
# -------------------------
st.title("📊 Ad Cost & Subscription Calculator")

# Load once
cpv_lookup = load_cpvs(CPV_FILE)
cps_lookup = load_cps(CPS_FILE)

# Initialize session state
if "cost_inr" not in st.session_state:
    st.session_state.cost_inr = None
    st.session_state.total_views = None
    st.session_state.breakdown = []

# 1) Inputs
total_subs = st.number_input("Total expected subscribers", min_value=0, value=1000, step=1)

mode = st.selectbox("Targeting mode", [
    "Worldwide",
    "Custom splits (country:views)",
    "Even split (by country list)"
])

if mode == "Worldwide":
    views = st.number_input("Total views", min_value=0, value=10000, step=1)

elif mode == "Custom splits (country:views)":
    st.write("Format: `India:5000, USA:2000`")
    splits = st.text_area("Country : Views splits")

else:
    # only keep entries whose name begins with a letter
    countries = sorted([c for c in cpv_lookup.keys() if c and c[0].isalpha()])

    selected = st.multiselect(
        "Select countries",
        countries,
        default=[]
    )

    views = st.number_input(
        "Total views (split evenly)",
        min_value=0,
        value=10000,
        step=1
    )


# 2) Calculate button — stores into session_state
if st.button("Calculate"):
    breakdown = []
    total_views = 0
    cost_inr = 0.0

    try:
        if mode == "Worldwide":
            cpv, cps = 0.22, 6.5
            vc, sc = views*cpv, total_subs*cps
            cost_inr, total_views = vc+sc, views
            breakdown += [
                f"Worldwide Views: {views}×₹{cpv:.2f} = ₹{vc:.2f}",
                f"Worldwide Subs:  {total_subs}×₹{cps:.2f} = ₹{sc:.2f}",
            ]

        elif mode == "Custom splits (country:views)":
            parts = [p.strip() for p in splits.split(",") if ":" in p]
            entries = []
            for p in parts:
                c, vstr = [x.strip() for x in p.split(":",1)]
                entries.append((c, c.casefold(), int(vstr)))
            total_v = sum(v for *_,v in entries)
            ideal = [total_subs*v/total_v for *_,v in entries]
            floors = [int(x) for x in ideal]
            rem = total_subs - sum(floors)
            fracs = sorted([(ideal[i]-floors[i],i) for i in range(len(floors))], reverse=True)
            for _,i in fracs[:rem]: floors[i]+=1

            for (c,k,v),subs in zip(entries,floors):
                cpv, cps = cpv_lookup[k], cps_lookup[k]
                vc, sc = v*cpv, subs*cps
                cost_inr += vc+sc
                total_views += v
                breakdown += [
                    f"{c.title()} Views: {v}×₹{cpv:.2f} = ₹{vc:.2f}",
                    f"{c.title()} Subs:  {subs}×₹{cps:.2f} = ₹{sc:.2f}",
                ]

        else:  # Even split
            n = len(selected)
            v_each, rv = divmod(views, n)
            s_each, rs = divmod(total_subs, n)
            for i,c in enumerate(selected):
                k = c
                v = v_each + (1 if i<rv else 0)
                s = s_each + (1 if i<rs else 0)
                cpv, cps = cpv_lookup[k], cps_lookup[k]
                vc, sc = v*cpv, s*cps
                cost_inr += vc+sc
                total_views += v
                breakdown += [
                    f"{c.title()} Views: {v}×₹{cpv:.2f} = ₹{vc:.2f}",
                    f"{c.title()} Subs:  {s}×₹{cps:.2f} = ₹{sc:.2f}",
                ]

        # store
        st.session_state.cost_inr = cost_inr
        st.session_state.total_views = total_views
        st.session_state.breakdown = breakdown

    except Exception as e:
        st.error(f"Calculation error: {e}")

# 3) If we have a stored result, show it (slider outside button)
if st.session_state.cost_inr is not None:
    st.subheader("📊 Cost Breakdown")
    for line in st.session_state.breakdown:
        st.write("-", line)
    st.write("**Total views:**", st.session_state.total_views)
    st.write("**Internal cost (INR):** ₹", f"{st.session_state.cost_inr:.2f}")

    markup = st.select_slider(
        "Profit markup %", 
        options=[40,45,50,55,60,65], 
        value=50,
        key="markup_slider"
    )
    i_inr, i_usd, c_inr, c_usd = calculate_cost(st.session_state.cost_inr, markup)
    st.markdown(f"**Cost to us:** ₹{i_inr} / ${i_usd}")
    st.markdown(f"**Offer to client (at {markup}% markup):** ₹{c_inr} / ${c_usd}")
