import streamlit as st
import pandas as pd
import altair as alt

# ---------- Page setup ----------
st.set_page_config(page_title="MLB Defensive Profiles", layout="wide")
st.title("MLB Defensive Profiles")

# ---------- Intro / site purpose ----------
with st.expander("What is this site? (click to expand)", expanded=True):
    st.markdown(
        """
The purpose of this tool is to show how different defensive metrics can show a different story about how good a player is at defense. 
I personally believe that the best way to evaluate defense is by the eye test, and that people cherry pick specific defensive metrics to prove a point. 
In reality, it is important to understand the nuances of each metric and understand how fundamentally, none are perfect. Advanced defensive stats simply aren't as advanced as offensive ones are, so they should be taken with a grain of salt.
        """
    )

# ---------- Config (same schema for both years) ----------
RAW_METRICS = ["outs_above_average", "Rdrs", "Rtot", "DRP", "Fld%", "FRV"]
PCT_METRICS = [
    "outs_above_average_percentile",
    "Rdrs_percentile",
    "Rtot_percentile",
    "DRP_percentile",
    "Fld%_percentile",
    "FRV_percentile",
]
LABEL = {
    "outs_above_average": "OAA",
    "outs_above_average_percentile": "OAA (pct)",
    "Rdrs": "DRS",
    "Rdrs_percentile": "DRS (pct)",
    "Rtot": "Total Zone",
    "Rtot_percentile": "Total Zone (pct)",
    "DRP": "DRP",
    "DRP_percentile": "DRP (pct)",
    "Fld%": "Fielding %",
    "Fld%_percentile": "Fielding % (pct)",
    "FRV": "FRV",
    "FRV_percentile": "FRV (pct)",
}
DATA_FILES = {
    "2025": "defensive_metrics_25.csv",
    "2024": "defensive_metrics_24.csv",
}

# ---------- Sidebar: season + filters ----------
with st.sidebar:
    st.header("Controls")
    season = st.radio("Season", options=list(DATA_FILES.keys()), index=0, horizontal=True)

@st.cache_data
def load_df(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Disagreement Index = std dev across percentile columns (NaNs are ignored row-wise)
    existing_pct = [c for c in PCT_METRICS if c in df.columns]
    df["disagreement_index"] = df[existing_pct].std(axis=1, ddof=0)
    return df

df = load_df(DATA_FILES[season])

with st.sidebar:
    team = st.selectbox("Filter players by team", ["(All)"] + sorted(df["Team"].unique().tolist()))
    candidates = df if team == "(All)" else df[df["Team"] == team]
    player = st.selectbox("Player", sorted(candidates["Player"].astype(str).unique()))

# Selected player row (use candidates to respect team filter)
row = candidates[candidates["Player"] == player].iloc[0]

# For this player: which percentile metrics actually have data?
player_pct_cols = [m for m in PCT_METRICS if m in df.columns and pd.notna(row[m])]

# ---------- Profile ----------
left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader(f"{row['Player']} · {row['Team']} · {season}")
    st.markdown(f"Innings: **{int(row['Inn'])}** &nbsp;|&nbsp; Age: **{row['Age']}**")
    st.markdown(f"Disagreement Index: **{row['disagreement_index']:.2f}**")

    # Story Splitter (clean UI, skip NaN metrics)
    if player_pct_cols:
        best = max(player_pct_cols, key=lambda m: row[m])
        worst = min(player_pct_cols, key=lambda m: row[m])
        bcol, wcol = st.columns(2)
        with bcol:
            st.success(
                f"**Best metric**\n\n{LABEL[best]} — **{row[best]:.0f}th**",
                icon="✅",
            )
        with wcol:
            st.warning(
                f"**Least favorable**\n\n{LABEL[worst]} — **{row[worst]:.0f}th**",
                icon="⚠️",
            )
    else:
        st.info("No percentile data available for this player.")

with right:
    st.subheader("Global Percentiles")
    if player_pct_cols:
        chart_df = pd.DataFrame({
            "Metric": [LABEL[m] for m in player_pct_cols],
            "Percentile": [row[m] for m in player_pct_cols],
        })
        # Altair bar chart with rotated, black x-labels
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("Metric:N", sort=None,
                        axis=alt.Axis(labelAngle=45, labelColor="black", title=None)),
                y=alt.Y("Percentile:Q", scale=alt.Scale(domain=[0, 100]),
                        title="Percentile (0–100)"),
                tooltip=["Metric:N", "Percentile:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.write("No percentile metrics to display for this player.")

st.divider()

# ---------- Raw vs Percentiles table (consistent horizontal align) ----------
st.subheader("Raw vs Percentiles")
table = pd.DataFrame({
    "Metric": [LABEL[m] for m in RAW_METRICS],
    "Raw":    [row[m] for m in RAW_METRICS],
    "Percentile (0–100)": [row[p] for p in PCT_METRICS],
})
# Use Styler + st.table for consistent alignment and N/A for missing
styler = (
    table.style
    .set_properties(**{"text-align": "center"})
    .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
    .format(precision=2, subset=["Raw"], na_rep="N/A")
    .format(precision=0, subset=["Percentile (0–100)"], na_rep="N/A")
)
st.table(styler)

st.divider()

# ---------- Leaderboard (with its own team filter) ----------
st.subheader(f"Leaderboards — {season}")
lc1, lc2, lc3 = st.columns([2, 1, 1])
with lc1:
    sort_metric = st.selectbox(
        "Sort by percentile metric",
        options=PCT_METRICS,
        format_func=lambda c: LABEL[c],
    )
with lc2:
    lb_team = st.selectbox("Team filter (leaderboard)", ["(All)"] + sorted(df["Team"].unique().tolist()))
with lc3:
    top_n = st.number_input("Top N", min_value=5, max_value=100, value=20, step=5)

lb_pool = df if lb_team == "(All)" else df[df["Team"] == lb_team]
# Remove players with no data for the chosen metric
lb_pool = lb_pool[lb_pool[sort_metric].notna()]

leader = (
    lb_pool.sort_values(sort_metric, ascending=False)
    [["Player", "Team", sort_metric, "disagreement_index"]]
    .head(int(top_n))
    .rename(columns={sort_metric: LABEL[sort_metric]})
)
leader_styler = (
    leader.style
    .set_properties(**{"text-align": "center"})
    .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
    .format(precision=0, subset=[LABEL[sort_metric]])
    .format(precision=2, subset=["disagreement_index"])
)
st.table(leader_styler)

st.divider()

# ---------- Glossary ----------
with st.expander("Glossary of defensive metrics"):
    st.markdown(
        """
### **Defensive Metrics Glossary**

- **OAA (Outs Above Average)** — *Statcast / Baseball Savant*  
  Quantifies **outs saved** relative to an average fielder using tracking data from every batted ball.  
  Accounts for **launch angle, exit velocity, direction**, and the **fielder’s starting position**, making it primarily a **range and reaction** metric.  
  Available since the Statcast tracking era (2016-present).

- **DRS (Defensive Runs Saved)** — *Sports Info Solutions (SIS)*  
  Converts defensive plays into **runs saved or cost** relative to league average.  
  Incorporates **range, throwing arm, double plays, positioning, and adjustments for specific field types**.  
  Available for modern seasons back to 2003.

- **Rtot (Total Zone Runs)** — *Baseball Reference*  
  Estimates how many **runs a player saved or allowed** compared to an average defender at their position, based on **balls hit into their zone**.  
  Derived from play-by-play data, so it covers seasons dating back to **1953**, making it useful for **historical comparison** when Statcast and DRS data are unavailable.

- **FRV (Fielding Run Value)** — *Statcast / Baseball Savant*  
  Expresses defensive performance in **runs saved or cost**, translating OAA-style tracking data into a **run-value scale**.  
  Integrates **range, positioning, and throw difficulty**.  
  Generally aligns with OAA directionally but provides a run-based interpretation.

- **DRP (Defensive Runs Prevented)** — *Baseball Prospectus*  
  Measures **runs prevented** relative to league average using **contextual play modeling**.  
  Incorporates **play difficulty, ballpark context, and positional adjustments** that differ from Statcast and SIS approaches.  
  Available for recent seasons and often diverges from Statcast-based systems.

- **Fielding Percentage (Fld%)** — *Traditional Statistic*  
  Calculated as **(Putouts + Assists) / (Putouts + Assists + Errors)**.  
  Simple to interpret but **ignores range and positioning**—a player who rarely reaches difficult balls can still have a perfect Fld%.

- **Disagreement Index** — *Custom Metric (in this app)*  
  Measures how much defensive systems **disagree** on a player’s ability by computing the **standard deviation across all percentile metrics**.  
  A higher value means greater inconsistency between systems’ evaluations.
        """
    )

# ---------- Credits ----------
st.caption(
    "Data sources: Statcast (Baseball Savant), Baseball Reference, and Baseball Prospectus (as available). "
    "Percentiles are global within the selected season. App by Adarsh Saranathan."
)
