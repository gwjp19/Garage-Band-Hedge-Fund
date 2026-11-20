import subprocess
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

df = pd.read_csv("trades.csv")

df = (df.drop_duplicates(["event_title", "game_start"])
        .sort_values("logged_at"))

open_bets = df[df["status"] == "open"].sort_values("game_start")
closed_bets = df[df["status"].isin(["settled", "void"])].sort_values("game_start")

closed_bets["profit"] = closed_bets["pnl"].sum

st.set_page_config(page_title="Garage Band Hedge Fund", layout="wide")
st.title("GBHF PNL Charts and Results")
st.write("This is an automatic hedging trader that seraches for price dicrepencies between Kalshi and Polymarket sports markets. Right now its being tested with paper money to make sure it survives outside the backtest")

if not closed_bets.empty:
  cost = closed_bets["total_cost"].sum
  profit = closed_bets["pnl"].sum
  ROI = profit/cost * 100
  
  SURFACE, INK, INK_2, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
  fig, ax = plt.subplots(figsize=(9, 4.5), facecolor=SURFACE)
  ax.set_facecolor(SURFACE)
  ax.axhline(0, color=INK_2, linewidth=1)
  ax.plot(closed_bets["settled_utc"], closed_bets["pnl"].cumsum(), color=SERIES, linewidth=2)
  for s in ("top", "right"):
    ax.spines[s].set_visible(False)
  for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
  ax.grid(True, color=GRID, linewidth=0.8)
  ax.tick_params(colors=INK_2, labelsize=9, length=0)
  ax.set_ylabel("Cumulative profit ($)", color=INK)
  fig.suptitle("Paper trading P&L", x=0.06, ha="left", fontsize=14, color=INK)
  ax.set_title(f"{len(closed_bets)} closed bets", loc="left", fontsize=9, color=INK_2)
  ax.plot(closed_bets["game_start"], closed_bets["profit"].cumsum(),
  color=SERIES, linewidth=2, label="Model")
  ax.plot(closed_bets["game_start"], closed_bets["opp_profit"].cumsum(),
  color="#d64545", linewidth=2, label="Opposite of model")
  ax.legend(frameon=False, fontsize=9)

  left, right = st.columns([2, 1])
  with left:
    st.pyplot(fig)
  with right:
    st.subheader("Profits")
    st.write(f"Total Profit: ${profit:,.2f}")
    st.write(f"Total amount wagered: ${wagers:,.2f}")
    st.write(f"ROI: {ROI:,.2f}%")

else:
    st.write("No settled bets yet.")

    




  
