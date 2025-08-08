import streamlit as st
import pandas as pd

# -------------------------
# Hard‑coded file paths
# -------------------------
CPV_FILE = "data/Cost_Conv_Location_CPV.csv"
CPS_FILE = "data/Cost_Conv_Location_CPS.csv"


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
    data.loc[data["CPV_INR"] == 0, "CPV_INR"] = 0.30

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

# Add this block below the title:
st.sidebar.markdown("""
                    

**Worlwide Targeted**
- **$50:** 5,000 views  
- **$100:** 10,000 views  
- **$150:** 15,000 views  
- **$200:** 20,000 views  
- **$249:** 25K views + 400-450 subs  
- **$299:** 32K views + 700-750 subs  
- **$399:** 50K views + 800-850 subs  
- **$499:** 80K views + 1.6k-2.4k subs  
- **$699:** 100K views + 2.8K-3.2K subs  
- **$999:** 160K views + 3.8K-4.2K subs  
- **$1,499:** 240K views + 6.2K-6.5K subs  
- **$1,999:** 325K views + 8K subs  
- **$2,499:** 415K views + 10K subs  
- **$3,000:** 520K views + 12K subs  
- **$3,500:** 620K views + 14K subs  
- **$4,000:** 730K views + 16K subs  
- **$4,500:** 850K views + 18K subs  
- **$5,000:** 1M views + 20K subs  


**United States Targeted**
- **$149:** 3.5K views  
- **$199:** 4.7K views  
- **$249:** 6K views  
- **$299:** 7.2K views  
- **$399:** 9.5K views  
- **$499:** 12.5K views  
- **$1,000:** 26K views   
""")

# Load once
cpv_lookup = load_cpvs(CPV_FILE)
cps_lookup = load_cps(CPS_FILE)

# Initialize session state
if "cost_inr" not in st.session_state:
    st.session_state.cost_inr = None
    st.session_state.total_views = None
    st.session_state.breakdown = []

# 1) Inputs
mode = st.selectbox("Targeting mode", [
    "Worldwide",
    "Custom splits (country:views)",
    "Even split (by country list)"
])

if mode == "Worldwide":
    min_views = 80000    # $499 minimum
    min_subs = 2000
    max_subs = int(0.05 * st.session_state.get("views", min_views))
    if 'views' not in st.session_state:
        st.session_state.views = min_views
    if 'subs' not in st.session_state:
        st.session_state.subs = min_subs

    views = st.number_input(
        "Total views (minimum for Worldwide is 80,000 views / $499)",
        min_value=min_views,
        value=st.session_state.views,
        step=1,
        key="views"
    )
    max_subs = int(0.05 * views)
    total_subs = st.number_input(
        f"Total expected subscribers (minimum 2,000, max {max_subs})",
        min_value=min_subs,
        max_value=max_subs,
        value=min(max(st.session_state.get("subs", min_subs), min_subs), max_subs),
        step=1,
        key="subs"
    )
    if views < min_views or total_subs < min_subs:
        st.warning("Minimum allowed for Worldwide is 80,000 views and 2,000 subscribers ($499 package).")
    if total_subs > max_subs:
        st.warning(f"Subscribers cannot exceed 5% of total views ({max_subs} for {views} views).")

elif mode == "Custom splits (country:views)":
    st.write("Format: `India:5000, USA:2000`")
    splits = st.text_area("Country : Views splits")
    views = 0
    try:
        parts = [p.strip() for p in splits.split(",") if ":" in p]
        views = sum(int(x.split(":")[1]) for x in parts)
    except Exception:
        pass
    max_subs = int(0.05 * views) if views > 0 else 1000000
    total_subs = st.number_input(
        f"Total expected subscribers (max {max_subs})",
        min_value=0,
        max_value=max_subs,
        value=500,
        step=1,
        key="subs"
    )
    if views > 0 and total_subs > max_subs:
        st.warning(f"Subscribers cannot exceed 5% of total views ({max_subs} for {views} views).")

else:
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
    max_subs = int(0.05 * views) if views > 0 else 1000000
    total_subs = st.number_input(
        f"Total expected subscribers (split evenly, max {max_subs})",
        min_value=0,
        max_value=max_subs,
        value=500,
        step=1,
        key="subs"
    )
    if views > 0 and total_subs > max_subs:
        st.warning(f"Subscribers cannot exceed 5% of total views ({max_subs} for {views} views).")


# 2) Calculate button — stores into session_state
if st.button("Calculate"):
    breakdown = []
    total_views = 0
    cost_inr = 0.0

    try:
        if mode == "Worldwide":
            cpv, cps = 0.20, 6.0
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

            for (c,k,v),subs in zip(entries, floors):
                 k = k.casefold() 
                 if k == "worldwide":
                    cpv, cps = 0.20, 6.0
                 else:
                     cpv = cpv_lookup.get(k, 0.30)
                     cps = cps_lookup.get(k, 10.0)

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

# 4) What can you get for $X?
st.header("💡 What can you get for $X?")
usd_input = st.number_input("Enter your budget in USD", min_value=50, value=500, step=1)
inr_budget = usd_input * 85  # Use your INR_TO_USD conversion if needed

tab1, tab2, tab3 = st.tabs(["Worldwide", "Custom split", "Even split"])

with tab1:
    # Use worldwide CPV/CPS
    cpv, cps = 0.20, 6.0
    # 5% subs-to-views ratio: cost = views*cpv + subs*cps, subs = 0.05*views
    # cost = views*cpv + (0.05*views)*cps = views*(cpv + 0.05*cps)
    if cpv + 0.05 * cps > 0:
        max_views = int(inr_budget / (cpv + 0.05 * cps))
        max_subs = int(0.05 * max_views)
        st.markdown(f"**Worldwide:** {max_views:,} views + {max_subs:,} subs")
        st.caption(f"CPV: ₹{cpv}, CPS: ₹{cps}, Budget: ₹{inr_budget:,.0f}")
    else:
        st.write("Invalid CPV/CPS values.")

with tab2:
    st.write("Enter your custom split (e.g. India:60, USA:40):")
    split_input = st.text_input("Country : % split", value="India:60, USA:40", key="split_budget")
    try:
        parts = [p.strip() for p in split_input.split(",") if ":" in p]
        split = [(x.split(":")[0].strip(), float(x.split(":")[1].strip())) for x in parts]
        total_percent = sum([p[1] for p in split])
        if total_percent > 0:
            for country, percent in split:
                country_key = country.casefold()
                country_budget = inr_budget * (percent / total_percent)
                cpv = cpv_lookup.get(country_key, 0.30)
                cps = cps_lookup.get(country_key, 10.0)
                if cpv + 0.05 * cps > 0:
                    views = int(country_budget / (cpv + 0.05 * cps))
                    subs = int(0.05 * views)
                    st.markdown(f"**{country.title()}:** {views:,} views + {subs:,} subs (₹{country_budget:,.0f})")
                else:
                    st.write(f"{country.title()}: Invalid CPV/CPS values.")
        else:
            st.write("Please enter valid percentages.")
    except Exception as e:
        st.write("Invalid input format.")

with tab3:
    st.write("Select countries for even split:")
    country_options = sorted([c.title() for c in cpv_lookup.keys() if c and c[0].isalpha()])
    # Only set defaults if present in options
    default_countries = []
    for d in ["India", "Usa", "United States"]:
        if d in country_options:
            default_countries.append(d)
    if not default_countries:
        default_countries = country_options[:2]  # fallback to first two
    even_countries = st.multiselect(
        "Countries",
        country_options,
        default=default_countries,
        key="even_budget"
    )
    n = len(even_countries)
    if n > 0:
        per_country_budget = inr_budget / n
        for country in even_countries:
            country_key = country.casefold()
            cpv = cpv_lookup.get(country_key, 0.30)
            cps = cps_lookup.get(country_key, 10.0)
            if cpv + 0.05 * cps > 0:
                views = int(per_country_budget / (cpv + 0.05 * cps))
                subs = int(0.05 * views)
                st.markdown(f"**{country}:** {views:,} views + {subs:,} subs (₹{per_country_budget:,.0f})")
            else:
                st.write(f"{country}: Invalid CPV/CPS values.")
    else:
        st.write("Select at least one country.")
