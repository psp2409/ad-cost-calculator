import sys
import pandas as pd

INR_TO_USD = 1 / 85  # Fixed conversion


# ---------- Smart CSV reader ----------

def _read_two_col_smart(filepath: str, value_col_name: str, value_name_hints: list[str] = None):
    """
    Robustly read 2+ column CSVs that might have title rows or be headerless.
    Returns a DataFrame with columns ['Country', value_col_name].
    """
    value_col_name = value_col_name.strip()
    value_name_hints = (value_name_hints or [])
    raw = pd.read_csv(filepath, header=None)

    if raw.shape[1] < 2:
        raise ValueError(f"{filepath} must have at least two columns.")

    first_second = pd.to_numeric(raw.iloc[0, 1], errors='coerce')
    if pd.notna(first_second):
        df = raw.iloc[:, :2].copy()
        df.columns = ["Country", value_col_name]
    else:
        dfh = pd.read_csv(filepath)
        dfh.columns = (dfh.columns.astype(str)
                       .str.replace('\xa0', ' ', regex=False)
                       .str.strip()
                       .str.replace(r'\s+', ' ', regex=True))
        country_col = next(
            (c for c in dfh.columns if any(k in c.lower() for k in ['country', 'territory', 'user location'])),
            dfh.columns[0]
        )
        value_col = next(
            (c for c in dfh.columns
             if any(h in c.lower() for h in [*value_name_hints, value_col_name.lower()])),
            dfh.columns[-1]
        )
        df = dfh[[country_col, value_col]].copy()
        df.columns = ["Country", value_col_name]

    df["Country"] = df["Country"].astype(str).str.strip()
    df[value_col_name] = pd.to_numeric(df[value_col_name], errors='coerce').fillna(0.0)
    return df


# ---------- Loaders returning lookup dicts ----------

def load_cpvs(filepath: str) -> dict[str, float]:
    """
    Reads a CSV that is either headerless or has a single header row.
    Always returns a dict mapping lowercase country → CPV_INR.
    """
    raw = pd.read_csv(filepath, header=None)
    if raw.shape[1] < 2:
        raise ValueError(f"{filepath} must have at least two columns.")
    # Detect header row: if cell (0,1) is not numeric, drop it
    first = pd.to_numeric(raw.iloc[0, 1], errors='coerce')
    if pd.isna(first):
        data = raw.iloc[1:, [0, 1]].copy()
    else:
        data = raw.iloc[:, [0, 1]].copy()
    data.columns = ["Country", "CPV_INR"]
    data["Country"] = data["Country"].astype(str).str.strip().str.casefold()
    data["CPV_INR"] = pd.to_numeric(data["CPV_INR"], errors='coerce').fillna(0)
    return dict(zip(data["Country"], data["CPV_INR"]))


def load_cps(filepath: str) -> dict[str, float]:
    """
    Reads a CSV that is either headerless or has a single header row.
    Always returns a dict mapping lowercase country → CPS_INR.
    Zero values are replaced with 10.0.
    """
    raw = pd.read_csv(filepath, header=None)
    if raw.shape[1] < 2:
        raise ValueError(f"{filepath} must have at least two columns.")
    first = pd.to_numeric(raw.iloc[0, 1], errors='coerce')
    if pd.isna(first):
        data = raw.iloc[1:, [0, 1]].copy()
    else:
        data = raw.iloc[:, [0, 1]].copy()
    data.columns = ["Country", "CPS_INR"]
    data["Country"] = data["Country"].astype(str).str.strip().str.casefold()
    data["CPS_INR"] = pd.to_numeric(data["CPS_INR"], errors='coerce').fillna(0)
    data.loc[data["CPS_INR"] == 0, "CPS_INR"] = 10.0
    return dict(zip(data["Country"], data["CPS_INR"]))


# ---------- Cost engine ----------

def calculate_cost(total_inr: float, markup_percent: float):
    client_inr = total_inr * (1 + markup_percent / 100.0)
    return (
        round(total_inr, 2),
        round(total_inr * INR_TO_USD, 2),
        round(client_inr, 2),
        round(client_inr * INR_TO_USD, 2),
    )


# ---------- Main ----------

if __name__ == "__main__":
    # --- Update these paths as needed ---
    cpv_file = r"C:\Users\Asus\Downloads\Costing_automation\data\Cost_Conv Location Wise - March to May 27th 2025 - Countrywise Avg Cpv - Infeed + Instream.csv"
    cps_file = r"C:\Users\Asus\Downloads\Costing_automation\data\Cost_Conv Location Wise - March to May 27th 2025 - Cost_Conv Location Wise - March to May 27th 2025.csv"
    # --------------------------------------

    cpv_lookup = load_cpvs(cpv_file)
    cps_lookup = load_cps(cps_file)

    targeting_input = input(
        "Enter targeting (worldwide OR country list OR country:views split): "
    ).strip().casefold()

    try:
        total_subs = int(input("Enter total number of subscribers expected: "))
    except ValueError:
        print("❌ Invalid subscriber count.")
        sys.exit(1)

    total_views = 0
    internal_cost_inr = 0.0
    breakdown = []

    # --- Worldwide fixed rates ---
    if targeting_input == "worldwide":
        try:
            views = int(input("Enter total views: "))
        except ValueError:
            print("❌ Invalid total views.")
            sys.exit(1)

        cpv_inr = 0.22
        cps_inr = 6.5

        view_cost = views * cpv_inr
        sub_cost = total_subs * cps_inr
        internal_cost_inr = view_cost + sub_cost
        total_views = views

        breakdown.append(f"Worldwide Views: {views} × ₹{cpv_inr:.2f} = ₹{view_cost:.2f}")
        breakdown.append(f"Worldwide Subs:  {total_subs} × ₹{cps_inr:.2f} = ₹{sub_cost:.2f}")

    # --- Custom "country:views" splits with proportional subscriber allocation ---
    elif ":" in targeting_input:
        parts = [p.strip() for p in targeting_input.split(",") if p.strip()]
        if not parts:
            print("❌ No countries provided.")
            sys.exit(1)

        # First, parse all views and keys
        entries = []
        for entry in parts:
            if ":" not in entry:
                print(f"❌ Invalid format: '{entry}'. Use country:views")
                sys.exit(1)
            country_raw, view_str = entry.split(":", 1)
            key = country_raw.strip().casefold()
            try:
                views = int(view_str.strip())
            except ValueError:
                print(f"❌ Invalid view count for '{country_raw}'.")
                sys.exit(1)
            if key not in cpv_lookup or key not in cps_lookup:
                print(f"❌ No CPV/CPS for '{country_raw}'. Available: {', '.join(sorted(cpv_lookup.keys()))}")
                sys.exit(1)
            entries.append((country_raw, key, views))

        # Sum total views in this custom split
        sum_views = sum(v for _, _, v in entries)
        if sum_views == 0:
            print("❌ Total views cannot be zero.")
            sys.exit(1)

        # Compute proportional subscribers
        ideal_subs = [total_subs * v / sum_views for _, _, v in entries]
        floor_subs = [int(x) for x in ideal_subs]
        leftover = total_subs - sum(floor_subs)

        # Distribute leftover based on largest fractional parts
        fracs = [(ideal_subs[i] - floor_subs[i], i) for i in range(len(floor_subs))]
        for _, idx in sorted(fracs, reverse=True)[:leftover]:
            floor_subs[idx] += 1

        # Now calculate costs
        for (country_raw, key, views), assigned_subs in zip(entries, floor_subs):
            cpv_inr = cpv_lookup[key]
            cps_inr = cps_lookup[key]

            vc = views * cpv_inr
            sc = assigned_subs * cps_inr
            internal_cost_inr += (vc + sc)
            total_views += views

            breakdown.append(f"{country_raw.title()} Views: {views} × ₹{cpv_inr:.2f} = ₹{vc:.2f}")
            breakdown.append(f"{country_raw.title()} Subs:  {assigned_subs} × ₹{cps_inr:.2f} = ₹{sc:.2f}")

    # --- Even split across listed countries ---
    else:
        countries = [c.strip() for c in targeting_input.split(",") if c.strip()]
        if not countries:
            print("❌ No countries provided.")
            sys.exit(1)

        try:
            views_total = int(input("Enter total number of views: "))
        except ValueError:
            print("❌ Invalid total views.")
            sys.exit(1)

        views_per_country = views_total // len(countries)
        leftover_views = views_total % len(countries)
        subs_per_country = total_subs // len(countries)
        leftover_subs = total_subs % len(countries)

        for i, country_raw in enumerate(countries):
            key = country_raw.casefold()
            if key not in cpv_lookup or key not in cps_lookup:
                print(f"❌ No CPV/CPS for '{country_raw}'. Available: {', '.join(sorted(cpv_lookup.keys()))}")
                sys.exit(1)

            cpv_inr = cpv_lookup[key]
            cps_inr = cps_lookup[key]

            v = views_per_country + (1 if i < leftover_views else 0)
            s = subs_per_country + (1 if i < leftover_subs else 0)

            vc = v * cpv_inr
            sc = s * cps_inr
            internal_cost_inr += (vc + sc)
            total_views += v

            breakdown.append(f"{country_raw.title()} Views: {v} × ₹{cpv_inr:.2f} = ₹{vc:.2f}")
            breakdown.append(f"{country_raw.title()} Subs:  {s} × ₹{cps_inr:.2f} = ₹{sc:.2f}")

    # ---- Output breakdown ----
    print("\n📊 Cost Breakdown:")
    for line in breakdown:
        print("  -", line)
    print(f"\n📦 Total Views: {total_views}")
    print(f"🧾 Internal Total Cost (INR): ₹{internal_cost_inr:.2f}")

    # ---- Profit margin selection & final quote ----
    print("\nChoose your profit margin:")
    markup_options = [40, 45, 50, 55, 60, 65]
    for idx, opt in enumerate(markup_options, 1):
        print(f"{idx}. {opt}%")

    try:
        choice = input("Enter your choice (1–6 or direct % like 43): ").strip()
        mi = int(choice)
        markup = (
            markup_options[mi - 1]
            if 1 <= mi <= len(markup_options)
            else mi
            if 1 <= mi <= 100
            else None
        )
        if markup is None:
            raise ValueError
    except Exception:
        print("❌ Invalid profit input.")
        sys.exit(1)

    internal_inr, internal_usd, client_inr, client_usd = calculate_cost(
        internal_cost_inr, markup
    )
    print(f"\n✅ Cost to us: ₹{internal_inr} / ${internal_usd}")
    print(f"💼 Offer to client (at {markup}% markup): ₹{client_inr} / ${client_usd}")
