import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FEE_CHANGE = pd.Timestamp("2026-11-21 16:16", tz=ET)   

st.set_page_config(page_title="Garage Band Hedge Fund", layout="wide")

DATA_URL = "https://raw.githubusercontent.com/gwjp19/Garage-Band-Hedge-Fund/main/data/trades.csv"

@st.cache_data(ttl=600)          
def load_trades():
    return pd.read_csv(DATA_URL)

df = load_trades()
df = df.drop_duplicates("trade_id")
df["settled_utc"] = pd.to_datetime(df["settled_utc"], utc=True, errors="coerce")

open_bets = df[df["status"] == "open"]
closed_bets = df[df["status"].isin(["settled", "MISMATCH"])].sort_values("settled_utc")
void_bet = df[df["status"].isin(["void", "MISMATCH"])].sort_values("settled_utc")
closed_bets["pnl"] = closed_bets["pnl"].fillna(0)
closed_bets["settled_et"] = closed_bets["settled_utc"].dt.tz_convert(ET)

st.title("GBHF PNL Charts and Results")

if not closed_bets.empty:
  cost = closed_bets["total_cost"].sum()
  profit = closed_bets["pnl"].sum()
  ROI = profit / cost * 100

  SURFACE, INK, INK_2, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
  fig, ax = plt.subplots(figsize=(9, 4.5), facecolor=SURFACE)
  ax.set_facecolor(SURFACE)
  ax.axhline(0, color=INK_2, linewidth=1)
  ax.plot(closed_bets["settled_et"], closed_bets["pnl"].cumsum(), color=SERIES, linewidth=2)
  ax.axvline(FEE_CHANGE, color=INK_2, linestyle="--", linewidth=1.2)
  ax.annotate("Fee raised to 0.095", xy=(FEE_CHANGE, 1), xycoords=("data", "axes fraction"),
              xytext=(-4, -4), textcoords="offset points", ha="right", va="top", fontsize=8, color=INK_2)
  ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %-I%p", tz=ET))
  for s in ("top", "right"):
    ax.spines[s].set_visible(False)
  for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
  ax.grid(True, color=GRID, linewidth=0.8)
  ax.tick_params(colors=INK_2, labelsize=9, length=0)
  ax.set_ylabel("Cumulative profit ($)", color=INK)
  ax.set_xlabel("Settled (Eastern time)", color=INK_2, fontsize=9)
  fig.suptitle("Paper trading P&L", x=0.06, ha="left", fontsize=14, color=INK)
  ax.set_title(f"{len(closed_bets)} closed bets", loc="left", fontsize=9, color=INK_2)
  fig.autofmt_xdate()

  left, right = st.columns([2, 1])
  with left:
    st.pyplot(fig)
  with right:
    st.subheader("Profits")
    st.write(f"Total Profit: ${profit:,.2f}")
    st.write(f"Total Capital Deployed: ${cost:,.2f}")
    st.write(f"ROI: {ROI:,.2f}%")

else:
    st.write("No settled bets yet.")

names = {
  "sport": "Sport",
  "team_on_kalshi": "Kalshi Trade",
  "kalshi_price": "Price on Kalshi",
  "kalshi_qty_avail": "Kalshi Qty Available",
  "kalshi_fee": "Kalshi Fee",
  "team_on_poly": "Polymarket Trade",
  "poly_price": "Price on Polymarket",
  "poly_qty_avail": "Poly Qty Available",
  "poly_fee": "Polymarket Fee",
  "total_cost": "Total Cost",
  "locked_profit": "Locked Profit",
  "pnl": "Profit",
  "quote_gap_sec": "Gap length",
}

tab_overview, tab_open, tab_closed, tab_void, contact = st.tabs(["Overview", "Open Trades", "Settled Trades", "Voided", "Contacts"])

with tab_overview:
  st.write("This scanner is built to take advantage of gaps between Polymarket US’s and Kalshi’s odds. During live games, the two markets can update at different speeds or move in different directions, sometimes only for a few seconds. When that happens, the scanner buys one team on one market and the other team on the other, but only when the pair costs less than $1 after fees. Because one of the two contracts always pays out $1, the profit is locked in no matter who wins, as long as both orders fill.")
  st.subheader("Process")
  st.write("- Game Matching")
  st.write("- Order Book Reading")
  st.write("- Price Checking (price must add up to less than $1 after fees)")
  st.write("- Logs Paper Trade")
  st.write("- Settling Trades After Game")
  st.write("The scanner started operating with a Polymarket US taker coefficient of 0.06 but has been updated to the true tier one 0.095. It will stay at 0.095 to ensure the scanner can work in less favorable conditions.The dotted line on the graph is when the change takes place.")
  st.subheader("Current Drawbacks")
  st.write("- Fills: Both orders have to be filled on two different sites, and if one misses the scanner is left holding a one sided trade")
  st.write("- Size: Many of these gaps will only have a few contracts available")
  st.write("- Capital: Money stays in each market until the game settles (about $29k at the bussiet point so far)")
  st.write("- Competition: Bots and professionals go after the same gaps")
  st.write("- Fees: The real teirs cut into every trade")
  st.write("- Settlement: The two venues could settle a game differently")
  st.write("- Track: It's paper trading over a short period")

with contact:
  st.write("I'm a current Mathematics student at Appalachian State University, I enjoy working with prediction markets, sports, and anything statistics or probability related. If you have any questions or advice for the scanner please reach out to me via:")
  st.link_button("LinkedIn","https://www.linkedin.com/in/george-porter-app",)
  st.write("If you want to play with the code:")
  st.link_button("GitHub", "https://github.com/gwjp19")
  st.write("This is a paper-trading experiment, not financial or betting advice")


with tab_open:
  st.write("Current Open Positions:")
  st.dataframe(
        open_bets[["sport","team_on_kalshi","kalshi_price","kalshi_qty_avail","kalshi_fee","team_on_poly","poly_price","poly_qty_avail","poly_fee","total_cost","locked_profit"]]
            .rename(columns=names)
            .round(2),
        hide_index=True,)

with tab_closed:
  st.write("Closed Positions:")
  st.dataframe(
        closed_bets[["sport","team_on_kalshi","kalshi_price","kalshi_qty_avail","kalshi_fee","team_on_poly","poly_price","poly_qty_avail","poly_fee","total_cost","pnl"]]
            .rename(columns=names)
            .round(2),
        hide_index=True,)

with tab_void:
    st.write("Voided Trades")
    st.dataframe(
        void_bet[["sport","team_on_kalshi","kalshi_price","kalshi_qty_avail","kalshi_fee","team_on_poly","poly_price","poly_qty_avail","poly_fee","total_cost","pnl"]]
            .rename(columns=names)
            .round(2),
        hide_index=True,)
  
