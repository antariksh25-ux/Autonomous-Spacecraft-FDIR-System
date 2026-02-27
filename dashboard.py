"""
dashboard.py
============
FDIR Ground Station — Interactive Command & Control Dashboard

Real-time Tkinter desktop dashboard for monitoring and commanding
the Autonomous Spacecraft FDIR System.

Key interactive features:
  - Human intervention panel: approve/execute recovery for escalated faults
  - Dynamic fault injection: pick subsystem + fault type + severity
  - Mission phase control, safe mode exit, operator annotations
  - Data analytics: BAR / PIE / HIST / TREND charts
  - Live scrolling event log with type filtering
  - Command history table with resolution tracking

The FDIR pipeline runs in a background daemon thread.
All state is read/written in-process via main.py shared objects.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk
import threading
import time
from collections import Counter, deque

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import main
import config as cfg
from recovery import RECOVERY_ACTIONS


# ══════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════

C = {
    "bg":       "#080c14",
    "panel":    "#0f1520",
    "card":     "#151d2c",
    "input":    "#1a2436",
    "border":   "#1e3a5f",
    "highlight":"#253550",
    "text":     "#d4dce8",
    "dim":      "#5a6a80",
    "cyan":     "#00c8e0",
    "green":    "#00e070",
    "yellow":   "#e8a820",
    "red":      "#e03030",
    "magenta":  "#d040d0",
    "blue":     "#3080e0",
    "orange":   "#e06020",
    "white":    "#ffffff",
    "alert_bg": "#1a0808",
    "alert_bdr":"#e03030",
}

FONT      = "Consolas"
FONT_UI   = ("Segoe UI", 9)
FONT_HEAD = (FONT, 11, "bold")
FONT_BODY = (FONT, 9)
FONT_SMALL= (FONT, 8)
FONT_TINY = (FONT, 7)
FONT_BIG  = (FONT, 14, "bold")

STATUS_COLORS = {
    "NOMINAL":            C["green"],
    "TEMPORARY_ANOMALY":  C["yellow"],
    "WARNING":            C["yellow"],
    "CRITICAL":           C["red"],
    "INITIALIZING":       C["dim"],
    "UNKNOWN":            C["dim"],
}

# All possible recovery actions an operator can choose
AVAILABLE_ACTIONS = [k for k in RECOVERY_ACTIONS.keys() if k != "none"]

# Fault types per subsystem for injection
INJECTABLE_FAULTS = {
    "power":   ["voltage_drop", "overcurrent", "battery_drain", "thermal_overload"],
    "thermal": ["thermal_runaway", "heater_failure", "radiator_degradation"],
}

INJECT_DEFAULTS = {
    "voltage_drop":         30.0,
    "overcurrent":          80.0,
    "battery_drain":        15.0,
    "thermal_overload":     90.0,
    "thermal_runaway":      88.0,
    "heater_failure":       10.0,
    "radiator_degradation": 55.0,
}


# ══════════════════════════════════════════════
# DASHBOARD CLASS
# ══════════════════════════════════════════════

class FDIRDashboard:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FDIR Ground Station \u2014 Command & Control")
        self.root.configure(bg=C["bg"])
        self.root.geometry("1340x860")
        self.root.minsize(1100, 720)

        self._start_time = time.time()
        self._last_log_idx = 0
        self._chart_mode = "bar"
        self._tick_counter = 0
        self._about_win = None
        self._sensor_history = deque(maxlen=300)
        self._prev_card_keys = []
        self._alert_flash = False
        self._pending_faults = []  # list of dicts for human intervention panel
        self._notifs = deque(maxlen=8)  # toast notifications
        self._log_filter = "ALL"

        self._setup_styles()
        self._build_ui()

        # Start FDIR loop
        threading.Thread(target=main.run_fdir_scenario, daemon=True).start()

        self.root.after(1200, self._tick_update)

    def run(self):
        self.root.mainloop()

    # ──────────────────────────────────────────
    # STYLES
    # ──────────────────────────────────────────

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("Dark.Treeview",
                     background=C["card"], foreground=C["text"],
                     fieldbackground=C["card"], borderwidth=0,
                     font=FONT_SMALL, rowheight=22)
        s.configure("Dark.Treeview.Heading",
                     background=C["panel"], foreground=C["cyan"],
                     font=(FONT, 8, "bold"), borderwidth=0)
        s.map("Dark.Treeview",
               background=[("selected", C["border"])],
               foreground=[("selected", C["cyan"])])

        s.configure("TCombobox",
                     fieldbackground=C["input"], background=C["input"],
                     foreground=C["text"], arrowcolor=C["cyan"],
                     borderwidth=0)

    # ──────────────────────────────────────────
    # UI CONSTRUCTION
    # ──────────────────────────────────────────

    def _build_ui(self):
        self._build_top_bar()
        self._build_status_strip()

        content = tk.Frame(self.root, bg=C["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)

        left = tk.Frame(content, bg=C["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        right = tk.Frame(content, bg=C["bg"], width=420)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)

        # Left: alert panel, commands + telemetry
        self._build_alert_panel(left)
        self._build_main_section(left)

        # Right: analytics + log
        self._build_analytics(right)
        self._build_log_panel(right)

        # Bottom: history + notifications
        self._build_bottom(self.root)

    # ──────────────────────────────────────────
    # TOP BAR
    # ──────────────────────────────────────────

    def _build_top_bar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=50)
        bar.pack(fill=tk.X, padx=2, pady=(2, 0))
        bar.pack_propagate(False)

        # Left button group
        btn_frame = tk.Frame(bar, bg=C["panel"])
        btn_frame.pack(side=tk.LEFT, padx=6, pady=6)

        for text, cmd, fg in [
            ("ABOUT", self._show_about, C["cyan"]),
            ("EXPORT LOG", self._export_log, C["dim"]),
        ]:
            tk.Button(btn_frame, text=text, bg=C["border"], fg=fg,
                      font=(FONT, 8, "bold"), relief=tk.FLAT, padx=10, pady=1,
                      activebackground=fg, activeforeground=C["bg"],
                      command=cmd, cursor="hand2"
                      ).pack(side=tk.LEFT, padx=2)

        # Title
        tk.Label(bar, text="\u2726  FDIR GROUND STATION \u2014 COMMAND & CONTROL  \u2726",
                 bg=C["panel"], fg=C["cyan"],
                 font=FONT_BIG).pack(side=tk.LEFT, padx=20)

        # MET + connection indicator
        right_fr = tk.Frame(bar, bg=C["panel"])
        right_fr.pack(side=tk.RIGHT, padx=12)

        self._conn_dot = tk.Label(right_fr, text="\u25cf CONNECTED",
                                  bg=C["panel"], fg=C["green"],
                                  font=FONT_SMALL)
        self._conn_dot.pack(side=tk.RIGHT, padx=(12, 0))

        self._met = tk.Label(right_fr, text="MET 00:00:00",
                             bg=C["panel"], fg=C["dim"],
                             font=(FONT, 12, "bold"))
        self._met.pack(side=tk.RIGHT)

    # ──────────────────────────────────────────
    # STATUS STRIP
    # ──────────────────────────────────────────

    def _build_status_strip(self):
        strip = tk.Frame(self.root, bg="#0a0e18", height=28)
        strip.pack(fill=tk.X, padx=2)
        strip.pack_propagate(False)

        self._ind = {}
        items = [
            ("mode",  "\u25cf FDIR ACTIVE",        C["green"]),
            ("phase", "\u25cf PHASE: NOMINAL_OPS",  C["cyan"]),
            ("pwr",   "\u25cf PWR: NOMINAL",        C["green"]),
            ("thrm",  "\u25cf THRM: NOMINAL",       C["green"]),
            ("tick",  "\u25cf TICK: T000",           C["dim"]),
            ("faults","\u25cf FAULTS: 0",           C["green"]),
        ]
        for key, txt, fg in items:
            lbl = tk.Label(strip, text=txt, bg="#0a0e18", fg=fg,
                           font=FONT_SMALL)
            lbl.pack(side=tk.LEFT, padx=10)
            self._ind[key] = lbl

        self._safe_lbl = tk.Label(strip, text="", bg="#0a0e18", fg=C["red"],
                                  font=(FONT, 9, "bold"))
        self._safe_lbl.pack(side=tk.RIGHT, padx=12)

    # ══════════════════════════════════════════
    # HUMAN INTERVENTION ALERT PANEL
    # ══════════════════════════════════════════

    def _build_alert_panel(self, parent):
        """
        Prominent panel that appears when faults are escalated to human.
        Shows full context and lets operator choose and execute actions.
        """
        self._alert_frame = tk.Frame(parent, bg=C["alert_bg"],
                                     highlightbackground=C["alert_bdr"],
                                     highlightthickness=2,
                                     highlightcolor=C["alert_bdr"])
        # Initially hidden — shown when human_hold_faults is non-empty

        # Header
        ahdr = tk.Frame(self._alert_frame, bg=C["alert_bg"])
        ahdr.pack(fill=tk.X, padx=8, pady=(8, 2))

        self._alert_icon = tk.Label(ahdr,
            text="\U0001f6a8  HUMAN INTERVENTION REQUIRED",
            bg=C["alert_bg"], fg=C["red"],
            font=(FONT, 12, "bold"))
        self._alert_icon.pack(side=tk.LEFT)

        self._alert_count = tk.Label(ahdr, text="0 PENDING",
                                     bg=C["red"], fg=C["white"],
                                     font=(FONT, 8, "bold"), padx=8)
        self._alert_count.pack(side=tk.RIGHT)

        # Container for individual fault cards
        self._alert_cards = tk.Frame(self._alert_frame, bg=C["alert_bg"])
        self._alert_cards.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._alert_visible = False

    def _refresh_alert_panel(self):
        """Rebuild the alert panel with current pending human-hold faults."""
        evts = self._events()

        # Gather pending faults from human_hold_faults + last diagnosis data
        with main.state_lock:
            holds = list(main.system_state.get("human_hold_faults", []))

        # Build context for each pending fault
        pending = []
        for ft in holds:
            ctx = {"fault_type": ft, "subsystem": "?", "confidence": "?",
                   "risk": "?", "reversibility": "?", "reasoning": "",
                   "recommended": "?", "human_msg": ""}

            for e in reversed(evts):
                et = e.get("event_type", "")
                d = e.get("data", {})
                if et == "FAULT_ISOLATED" and d.get("fault_type") == ft:
                    ctx["subsystem"]     = d.get("subsystem", "?")
                    ctx["confidence"]    = d.get("confidence_pct", "?")
                    ctx["risk"]          = d.get("risk_level", "?")
                    ctx["reversibility"] = d.get("reversibility", "?")
                    ctx["recommended"]   = d.get("recommended_action", "?")
                    break
            for e in reversed(evts):
                et = e.get("event_type", "")
                d = e.get("data", {})
                if et == "ETHICAL_DECISION" and d.get("autonomy_level") == "HUMAN_ESCALATION":
                    if d.get("subsystem") == ctx["subsystem"] or ctx["subsystem"] == "?":
                        ctx["reasoning"]  = d.get("reasoning", "")
                        ctx["human_msg"]  = d.get("human_message", "")
                        if ctx["subsystem"] == "?":
                            ctx["subsystem"] = d.get("subsystem", "?")
                        break
            pending.append(ctx)

        self._pending_faults = pending

        # Show / hide
        if pending and not self._alert_visible:
            self._alert_frame.pack(fill=tk.X, pady=(0, 3), before=self._main_frame)
            self._alert_visible = True
        elif not pending and self._alert_visible:
            self._alert_frame.pack_forget()
            self._alert_visible = False

        if not pending:
            return

        self._alert_count.configure(text=f"{len(pending)} PENDING")

        # Flash effect
        self._alert_flash = not self._alert_flash
        bdr = C["red"] if self._alert_flash else C["orange"]
        self._alert_frame.configure(highlightbackground=bdr)

        # Rebuild cards
        for w in self._alert_cards.winfo_children():
            w.destroy()

        for pf in pending:
            self._build_pending_fault_card(pf)

    def _build_pending_fault_card(self, ctx):
        """Build an interactive card for one pending human-hold fault."""
        card = tk.Frame(self._alert_cards, bg=C["card"],
                        highlightbackground=C["magenta"],
                        highlightthickness=1, highlightcolor=C["magenta"])
        card.pack(fill=tk.X, pady=3)

        # Top row: fault info
        top = tk.Frame(card, bg=C["card"])
        top.pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(top,
            text=f"\u26a0  {ctx['fault_type'].upper().replace('_',' ')}",
            bg=C["card"], fg=C["red"],
            font=(FONT, 10, "bold")).pack(side=tk.LEFT)

        tk.Label(top,
            text=f"[{ctx['subsystem'].upper()}]",
            bg=C["card"], fg=C["cyan"],
            font=FONT_BODY).pack(side=tk.LEFT, padx=8)

        # Stats row
        stats = tk.Frame(card, bg=C["card"])
        stats.pack(fill=tk.X, padx=8, pady=2)

        for label, val, fg in [
            ("CONF", ctx["confidence"], C["yellow"]),
            ("RISK", ctx["risk"], C["red"] if ctx["risk"] == "HIGH" else C["yellow"]),
            ("REV",  ctx["reversibility"], C["green"] if ctx["reversibility"] == "HIGH" else C["yellow"]),
        ]:
            tk.Label(stats, text=f"{label}: {val}",
                     bg=C["card"], fg=fg,
                     font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 16))

        # Reasoning
        if ctx.get("human_msg"):
            msg_text = ctx["human_msg"][:200]
            tk.Label(card, text=msg_text, bg=C["card"], fg=C["dim"],
                     font=FONT_TINY, wraplength=600, justify=tk.LEFT,
                     anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        # Action row: dropdown + execute button
        act_row = tk.Frame(card, bg=C["card"])
        act_row.pack(fill=tk.X, padx=8, pady=(4, 8))

        tk.Label(act_row, text="ACTION:", bg=C["card"], fg=C["dim"],
                 font=FONT_SMALL).pack(side=tk.LEFT)

        # Pre-select recommended action
        action_var = tk.StringVar(
            value=ctx["recommended"] if ctx["recommended"] in AVAILABLE_ACTIONS
                  else AVAILABLE_ACTIONS[0])

        cb = ttk.Combobox(act_row, textvariable=action_var,
                          values=AVAILABLE_ACTIONS, state="readonly",
                          font=FONT_SMALL, width=28)
        cb.pack(side=tk.LEFT, padx=6)

        tk.Button(act_row,
            text="\u2714  APPROVE & EXECUTE",
            bg=C["green"], fg=C["bg"],
            font=(FONT, 9, "bold"), relief=tk.FLAT, padx=12,
            activebackground="#00ff90", activeforeground=C["bg"],
            cursor="hand2",
            command=lambda ft=ctx["fault_type"], sub=ctx["subsystem"], av=action_var:
                self._cmd_approve_execute(ft, sub, av.get())
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(act_row,
            text="\u2716 DISMISS",
            bg=C["card"], fg=C["yellow"],
            font=FONT_SMALL, relief=tk.FLAT, padx=8,
            activebackground=C["yellow"], activeforeground=C["bg"],
            cursor="hand2",
            command=lambda ft=ctx["fault_type"]:
                self._cmd_dismiss_hold(ft)
        ).pack(side=tk.LEFT, padx=2)

    # ══════════════════════════════════════════
    # MAIN SECTION (fault cards + commands + telemetry)
    # ══════════════════════════════════════════

    def _build_main_section(self, parent):
        self._main_frame = tk.Frame(parent, bg=C["bg"])
        self._main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = tk.Frame(self._main_frame, bg=C["panel"])
        hdr.pack(fill=tk.X, pady=(0, 2))
        tk.Label(hdr, text="\u25b8  OPERATIONS & TELEMETRY",
                 bg=C["panel"], fg=C["cyan"],
                 font=FONT_HEAD).pack(side=tk.LEFT, padx=10, pady=5)
        self._fault_badge = tk.Label(hdr, text="0 ACTIVE FAULTS",
                                     bg=C["green"], fg=C["white"],
                                     font=(FONT, 8, "bold"), padx=8)
        self._fault_badge.pack(side=tk.RIGHT, padx=10, pady=5)

        # Fault cards row
        self._cards_frame = tk.Frame(self._main_frame, bg=C["bg"])
        self._cards_frame.pack(fill=tk.X, pady=(0, 2))

        # Bottom split: commands | telemetry
        bot = tk.Frame(self._main_frame, bg=C["bg"])
        bot.pack(fill=tk.BOTH, expand=True)

        self._build_commands(bot)
        self._build_telemetry(bot)

    # ──────────────────────────────────────────
    # GROUND COMMANDS
    # ──────────────────────────────────────────

    def _build_commands(self, parent):
        frm = tk.Frame(parent, bg=C["panel"], width=290)
        frm.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 2))
        frm.pack_propagate(False)

        tk.Label(frm, text="\u25b8  GROUND COMMANDS",
                 bg=C["panel"], fg=C["cyan"],
                 font=FONT_HEAD).pack(anchor=tk.W, padx=8, pady=(8, 4))

        # ── Mission phase ──
        sec = tk.Frame(frm, bg=C["panel"])
        sec.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(sec, text="MISSION PHASE", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).pack(anchor=tk.W)
        self._phase_var = tk.StringVar(value=cfg.MISSION_PHASE)
        cb = ttk.Combobox(sec, textvariable=self._phase_var,
                          values=list(cfg.MISSION_PHASE_CRITICALITY.keys()),
                          state="readonly", font=FONT_SMALL)
        cb.pack(fill=tk.X, pady=(0, 4))
        cb.bind("<<ComboboxSelected>>", self._cmd_phase)

        self._sep(frm)

        # ── Fault injection ──
        tk.Label(frm, text="FAULT INJECTION", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).pack(anchor=tk.W, padx=10, pady=(4, 2))

        inject_fr = tk.Frame(frm, bg=C["panel"])
        inject_fr.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(inject_fr, text="SUB:", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).grid(row=0, column=0, sticky=tk.W)
        self._inj_sub = tk.StringVar(value="power")
        csub = ttk.Combobox(inject_fr, textvariable=self._inj_sub,
                            values=["power", "thermal"], state="readonly",
                            font=FONT_SMALL, width=9)
        csub.grid(row=0, column=1, padx=2, pady=1, sticky=tk.EW)
        csub.bind("<<ComboboxSelected>>", self._update_inject_types)

        tk.Label(inject_fr, text="TYPE:", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).grid(row=1, column=0, sticky=tk.W)
        self._inj_type = tk.StringVar(value="voltage_drop")
        self._inj_cb = ttk.Combobox(inject_fr, textvariable=self._inj_type,
                            values=INJECTABLE_FAULTS["power"], state="readonly",
                            font=FONT_SMALL, width=20)
        self._inj_cb.grid(row=1, column=1, padx=2, pady=1, sticky=tk.EW)

        inject_fr.columnconfigure(1, weight=1)

        tk.Button(frm, text="\u26a1  INJECT FAULT",
                  bg=C["yellow"], fg=C["bg"],
                  font=(FONT, 9, "bold"), relief=tk.FLAT,
                  activebackground="#ffc040", activeforeground=C["bg"],
                  command=self._cmd_inject, cursor="hand2"
                  ).pack(fill=tk.X, padx=10, pady=4)

        self._sep(frm)

        # ── Force action ──
        tk.Label(frm, text="FORCE RECOVERY ACTION", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).pack(anchor=tk.W, padx=10, pady=(4, 2))

        force_fr = tk.Frame(frm, bg=C["panel"])
        force_fr.pack(fill=tk.X, padx=10, pady=2)

        self._force_sub = tk.StringVar(value="power")
        ttk.Combobox(force_fr, textvariable=self._force_sub,
                     values=["power", "thermal"], state="readonly",
                     font=FONT_SMALL, width=9
                     ).pack(side=tk.LEFT, padx=(0, 4))
        self._force_act = tk.StringVar(value="reduce_load")
        ttk.Combobox(force_fr, textvariable=self._force_act,
                     values=AVAILABLE_ACTIONS, state="readonly",
                     font=FONT_SMALL
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(frm, text="\u25b6  EXECUTE OVERRIDE",
                  bg=C["orange"], fg=C["white"],
                  font=(FONT, 8, "bold"), relief=tk.FLAT,
                  activebackground="#ff8040", activeforeground=C["bg"],
                  command=self._cmd_force_action, cursor="hand2"
                  ).pack(fill=tk.X, padx=10, pady=4)

        self._sep(frm)

        # ── Operator note ──
        tk.Label(frm, text="OPERATOR NOTE", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).pack(anchor=tk.W, padx=10, pady=(4, 2))
        self._note_entry = tk.Entry(frm, bg=C["input"], fg=C["text"],
                                    font=FONT_SMALL, insertbackground=C["cyan"],
                                    relief=tk.FLAT, bd=4)
        self._note_entry.pack(fill=tk.X, padx=10, pady=2)
        self._note_entry.bind("<Return>", lambda e: self._cmd_annotate())
        tk.Button(frm, text="\U0001f4ac  SEND NOTE",
                  bg=C["card"], fg=C["cyan"],
                  font=FONT_SMALL, relief=tk.FLAT,
                  command=self._cmd_annotate, cursor="hand2"
                  ).pack(fill=tk.X, padx=10, pady=(0, 4))

        self._sep(frm)

        # ── Bottom buttons ──
        bbf = tk.Frame(frm, bg=C["panel"])
        bbf.pack(fill=tk.X, padx=8, pady=4)

        for i, (text, fg, cmd) in enumerate([
            ("\u27f2 RESET",        C["red"],    self._cmd_reset),
            ("\u21bb REFRESH",      C["cyan"],   self._cmd_refresh),
            ("\u23f9 EXIT SAFE",    C["green"],  self._cmd_exit_safe),
        ]):
            b = tk.Button(bbf, text=text, bg=C["card"], fg=fg,
                          font=(FONT, 8, "bold"), relief=tk.FLAT,
                          activebackground=fg, activeforeground=C["bg"],
                          command=cmd, cursor="hand2", height=1)
            b.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            bbf.columnconfigure(i, weight=1)

    # ──────────────────────────────────────────
    # LIVE TELEMETRY
    # ──────────────────────────────────────────

    def _build_telemetry(self, parent):
        frm = tk.Frame(parent, bg=C["panel"])
        frm.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        for sub_name, bar_store_attr, params in [
            ("POWER", "_pwr_bars", [
                ("voltage",     "VOLTAGE",     "V"),
                ("current",     "CURRENT",     "A"),
                ("soc",         "SOC",         "%"),
                ("temperature", "TEMP (REG)",  "\u00b0C"),
            ]),
            ("THERMAL", "_thrm_bars", [
                ("internal_temp", "INT TEMP",   "\u00b0C"),
                ("radiator_temp", "RAD TEMP",   "\u00b0C"),
                ("heater_power",  "HEATER",     "%"),
                ("panel_temp",    "PANEL TEMP", "\u00b0C"),
            ]),
        ]:
            tk.Label(frm, text=f"\u25b8  LIVE TELEMETRY \u2014 {sub_name}",
                     bg=C["panel"], fg=C["cyan"],
                     font=(FONT, 10, "bold")).pack(anchor=tk.W, padx=10, pady=(8, 3))
            pf = tk.Frame(frm, bg=C["panel"])
            pf.pack(fill=tk.X, padx=10, pady=(0, 4))

            nom = cfg.POWER_NOMINAL if sub_name == "POWER" else cfg.THERMAL_NOMINAL
            bars = {}
            for key, label, unit in params:
                rng = nom[key]
                self._make_bar(pf, key, label, unit, rng, bars)
            setattr(self, bar_store_attr, bars)

    def _make_bar(self, parent, key, label, unit, rng, store):
        row = tk.Frame(parent, bg=C["panel"])
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=label, bg=C["panel"], fg=C["dim"],
                 font=FONT_SMALL, width=12, anchor=tk.W).pack(side=tk.LEFT)
        cv = tk.Canvas(row, bg=C["card"], height=16, highlightthickness=0, bd=0)
        cv.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        vl = tk.Label(row, text=f"{rng['nominal']:.1f} {unit}",
                      bg=C["panel"], fg=C["text"],
                      font=(FONT, 9, "bold"), width=10, anchor=tk.E)
        vl.pack(side=tk.RIGHT)
        store[key] = {"cv": cv, "vl": vl, "min": rng["min"],
                      "max": rng["max"], "unit": unit}

    # ──────────────────────────────────────────
    # DATA ANALYTICS (RIGHT TOP)
    # ──────────────────────────────────────────

    def _build_analytics(self, parent):
        frm = tk.Frame(parent, bg=C["panel"])
        frm.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        hdr = tk.Frame(frm, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="DATA ANALYTICS", bg=C["panel"], fg=C["cyan"],
                 font=FONT_HEAD).pack(side=tk.LEFT, padx=10, pady=5)

        tabs = tk.Frame(hdr, bg=C["panel"])
        tabs.pack(side=tk.RIGHT, padx=8)
        self._chart_btns = {}
        for t in ["BAR", "PIE", "HIST", "TREND"]:
            b = tk.Button(tabs, text=t, bg=C["card"], fg=C["dim"],
                          font=(FONT, 7, "bold"), relief=tk.FLAT, padx=6, pady=1,
                          command=lambda m=t.lower(): self._switch_chart(m),
                          cursor="hand2")
            b.pack(side=tk.LEFT, padx=1)
            self._chart_btns[t.lower()] = b
        self._chart_btns["bar"].configure(bg=C["border"], fg=C["cyan"])

        self._fig = Figure(figsize=(4.5, 2.6), dpi=90)
        self._fig.patch.set_facecolor(C["card"])
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(C["card"])
        self._canvas_chart = FigureCanvasTkAgg(self._fig, master=frm)
        self._canvas_chart.get_tk_widget().pack(
            fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # ──────────────────────────────────────────
    # EVENT LOG (RIGHT BOTTOM)
    # ──────────────────────────────────────────

    def _build_log_panel(self, parent):
        frm = tk.Frame(parent, bg=C["panel"])
        frm.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(frm, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="EVENT LOG", bg=C["panel"], fg=C["cyan"],
                 font=FONT_HEAD).pack(side=tk.LEFT, padx=10, pady=5)

        # Filter
        flt_fr = tk.Frame(hdr, bg=C["panel"])
        flt_fr.pack(side=tk.RIGHT, padx=8)
        tk.Label(flt_fr, text="FILTER:", bg=C["panel"], fg=C["dim"],
                 font=FONT_TINY).pack(side=tk.LEFT)
        self._log_filter_var = tk.StringVar(value="ALL")
        flt = ttk.Combobox(flt_fr, textvariable=self._log_filter_var,
                           values=["ALL", "FAULTS", "DECISIONS", "RECOVERY",
                                   "HUMAN", "SYSTEM"],
                           state="readonly", font=FONT_TINY, width=10)
        flt.pack(side=tk.LEFT, padx=4)
        flt.bind("<<ComboboxSelected>>", lambda _: self._refilter_log())

        self._log_cnt = tk.Label(hdr, text="0", bg=C["green"],
                                 fg=C["bg"], font=(FONT, 7, "bold"), padx=6)
        self._log_cnt.pack(side=tk.RIGHT, padx=4, pady=5)

        box = tk.Frame(frm, bg=C["card"])
        box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self._log = tk.Text(box, bg=C["card"], fg=C["text"],
                            font=FONT_SMALL, wrap=tk.WORD, relief=tk.FLAT,
                            borderwidth=0, padx=6, pady=4,
                            state=tk.DISABLED, cursor="arrow")
        sb = tk.Scrollbar(box, command=self._log.yview,
                          bg=C["panel"], troughcolor=C["card"])
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for tag, fg in [
            ("inject",   C["red"]),    ("anomaly",  C["yellow"]),
            ("isolate",  C["orange"]), ("dec_full", C["green"]),
            ("dec_lim",  C["yellow"]), ("dec_hum",  C["magenta"]),
            ("recover",  C["green"]),  ("safe",     C["red"]),
            ("nominal",  C["green"]),  ("system",   C["cyan"]),
            ("dim",      C["dim"]),    ("note",     C["magenta"]),
            ("human",    C["magenta"]),("ok",       C["green"]),
        ]:
            self._log.tag_configure(tag, foreground=fg)

    # ──────────────────────────────────────────
    # BOTTOM: HISTORY + NOTIFICATIONS
    # ──────────────────────────────────────────

    def _build_bottom(self, parent):
        wrapper = tk.Frame(parent, bg=C["bg"])
        wrapper.pack(fill=tk.X, padx=2, pady=(0, 2))

        # Command history table
        hist_fr = tk.Frame(wrapper, bg=C["panel"], height=170)
        hist_fr.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        hist_fr.pack_propagate(False)

        hdr = tk.Frame(hist_fr, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="COMMAND HISTORY & RESOLUTION LOG",
                 bg=C["panel"], fg=C["cyan"],
                 font=FONT_HEAD).pack(side=tk.LEFT, padx=10, pady=5)
        self._hist_cnt = tk.Label(hdr, text="0", bg=C["cyan"],
                                  fg=C["bg"], font=(FONT, 7, "bold"), padx=6)
        self._hist_cnt.pack(side=tk.RIGHT, padx=10, pady=5)

        cols = ("tick", "subsystem", "fault_type", "confidence",
                "risk", "decision", "action", "status")
        self._tree = ttk.Treeview(hist_fr, columns=cols, show="headings",
                                  style="Dark.Treeview", height=5)
        for cid, head, w in [
            ("tick",       "TICK",       55),
            ("subsystem",  "SUBSYSTEM",  85),
            ("fault_type", "FAULT TYPE", 155),
            ("confidence", "CONF",       75),
            ("risk",       "RISK",       60),
            ("decision",   "DECISION",   145),
            ("action",     "ACTION",     180),
            ("status",     "STATUS",     85),
        ]:
            self._tree.heading(cid, text=head)
            self._tree.column(cid, width=w, minwidth=40)

        ts = tk.Scrollbar(hist_fr, command=self._tree.yview)
        self._tree.configure(yscrollcommand=ts.set)
        ts.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=(0, 6))
        self._tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        for tag, fg in [("full", C["green"]), ("limited", C["yellow"]),
                        ("escalated", C["magenta"]), ("pending", C["red"]),
                        ("human", C["green"])]:
            self._tree.tag_configure(tag, foreground=fg)

        # Notification strip
        self._notif_frame = tk.Frame(wrapper, bg=C["bg"], width=260)
        self._notif_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 0))
        self._notif_frame.pack_propagate(False)

        tk.Label(self._notif_frame, text="NOTIFICATIONS",
                 bg=C["bg"], fg=C["dim"],
                 font=FONT_TINY).pack(anchor=tk.W, padx=4, pady=(4, 2))

        self._notif_text = tk.Text(self._notif_frame, bg=C["card"],
                                   fg=C["text"], font=FONT_TINY,
                                   wrap=tk.WORD, relief=tk.FLAT,
                                   state=tk.DISABLED, padx=4, pady=4,
                                   cursor="arrow", bd=0)
        self._notif_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 4))
        for tag, fg in [
            ("info", C["cyan"]), ("warn", C["yellow"]),
            ("error", C["red"]), ("ok", C["green"]),
        ]:
            self._notif_text.tag_configure(tag, foreground=fg)

    # ══════════════════════════════════════════
    # UPDATE LOOP
    # ══════════════════════════════════════════

    def _tick_update(self):
        self._tick_counter += 1
        try:
            # MET
            elapsed = time.time() - self._start_time
            h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
            self._met.configure(text=f"MET {h:02d}:{m:02d}:{s:02d}")

            with main.state_lock:
                st = dict(main.system_state)
                subs = {k: dict(v) for k, v in st.get("subsystems", {}).items()}

            self._refresh_indicators(st, subs)
            self._refresh_bars(subs)
            self._refresh_log()
            self._refresh_alert_panel()

            if self._tick_counter % 2 == 0:
                self._refresh_cards()
            if self._tick_counter % 3 == 0:
                self._refresh_history()
            if self._tick_counter % 5 == 0:
                self._refresh_chart()
        except Exception:
            pass
        self.root.after(1000, self._tick_update)

    # ──────────────────────────────────────────
    # REFRESH: Status Indicators
    # ──────────────────────────────────────────

    def _refresh_indicators(self, st, subs):
        phase = st.get("mission_phase", "?")
        crit = st.get("mission_criticality", "LOW")
        pcol = {"LOW": C["green"], "MEDIUM": C["yellow"], "HIGH": C["red"]}.get(crit, C["dim"])
        self._ind["phase"].configure(text=f"\u25cf PHASE: {phase}", fg=pcol)
        self._phase_var.set(phase)

        for key, sub_name in [("pwr", "power"), ("thrm", "thermal")]:
            s = subs.get(sub_name, {}).get("status", "UNKNOWN")
            self._ind[key].configure(
                text=f"\u25cf {key.upper()}: {s}",
                fg=STATUS_COLORS.get(s, C["dim"]))

        tick = st.get("tick", 0)
        self._ind["tick"].configure(text=f"\u25cf TICK: T{tick:03d}", fg=C["cyan"])

        n = len(st.get("active_faults", []))
        self._ind["faults"].configure(
            text=f"\u25cf FAULTS: {n}",
            fg=C["red"] if n else C["green"])
        self._fault_badge.configure(
            text=f"{n} ACTIVE FAULTS",
            bg=C["red"] if n else C["green"])

        # Connection dot color
        running = st.get("running", False)
        self._conn_dot.configure(
            text="\u25cf CONNECTED" if running else "\u25cf OFFLINE",
            fg=C["green"] if running else C["red"])

        # Safe mode indicator
        if st.get("safe_mode_active"):
            self._safe_lbl.configure(text="\U0001f6e1 SAFE MODE ACTIVE")
        else:
            self._safe_lbl.configure(text="")

    # ──────────────────────────────────────────
    # REFRESH: Telemetry Bars
    # ──────────────────────────────────────────

    def _refresh_bars(self, subs):
        self._draw_bars("power", self._pwr_bars, subs)
        self._draw_bars("thermal", self._thrm_bars, subs)

        pd = subs.get("power", {}).get("sensor_data", {})
        td = subs.get("thermal", {}).get("sensor_data", {})
        if pd and td:
            with main.state_lock:
                tick = main.system_state.get("tick", 0)
            self._sensor_history.append({
                "tick": tick,
                "pwr_v": pd.get("voltage", 0),
                "pwr_i": pd.get("current", 0),
                "thrm_int": td.get("internal_temp", 0),
                "thrm_rad": td.get("radiator_temp", 0),
            })

    def _draw_bars(self, sub_name, bar_dict, subs):
        data = subs.get(sub_name, {}).get("sensor_data", {})
        hr = subs.get(sub_name, {}).get("health_report", {})
        params = hr.get("parameters", {})
        for key, info in bar_dict.items():
            val = data.get(key, info["min"])
            ps = params.get(key, {}).get("status", "NOMINAL")
            cv = info["cv"]
            cv.delete("all")
            w = cv.winfo_width()
            h = cv.winfo_height()
            if w < 5:
                continue
            ratio = max(0.0, min(1.0,
                        (val - info["min"]) / (info["max"] - info["min"] + 0.01)))
            col = STATUS_COLORS.get(ps, C["cyan"])

            # Background track
            cv.create_rectangle(0, 0, w, h, fill=C["input"], outline="")
            # Fill
            fill_w = int(ratio * w)
            if fill_w > 0:
                cv.create_rectangle(0, 0, fill_w, h, fill=col, outline="")
            # Nominal marker
            nom_ratio = 0.5
            nx = int(nom_ratio * w)
            cv.create_line(nx, 0, nx, h, fill=C["dim"], dash=(2, 2))

            info["vl"].configure(text=f"{val:.1f} {info['unit']}", fg=col)

    # ──────────────────────────────────────────
    # REFRESH: Fault Cards
    # ──────────────────────────────────────────

    def _refresh_cards(self):
        evts = self._events()
        cards = []
        isolations = []
        decisions = {}

        for e in evts:
            et = e.get("event_type", "")
            d = e.get("data", {})
            tick = e.get("tick", 0)
            if et == "FAULT_ISOLATED":
                isolations.append({
                    "tick": tick, "sub": d.get("subsystem", "?"),
                    "ft": d.get("fault_type", "?"),
                    "conf": d.get("confidence_pct", "?"),
                })
            elif et == "ETHICAL_DECISION":
                decisions[tick] = {
                    "level":  d.get("autonomy_level", "?"),
                    "action": d.get("permitted_action", "?"),
                }

        for iso in isolations:
            dec = decisions.get(iso["tick"], {})
            iso["decision"] = dec.get("level", "PENDING")
            iso["action"]   = dec.get("action", "\u2014")
            cards.append(iso)

        cards = cards[-5:]
        keys = [(c["tick"], c["ft"]) for c in cards]
        if keys == self._prev_card_keys:
            return
        self._prev_card_keys = keys

        for w in self._cards_frame.winfo_children():
            w.destroy()

        for i, c in enumerate(cards):
            lev = c["decision"]
            if lev == "FULL_AUTONOMOUS":
                bdr, sym, dtxt = C["green"], "\u2705", "AUTO"
            elif lev == "LIMITED_ACTION":
                bdr, sym, dtxt = C["yellow"], "\u26a0", "LIMITED"
            elif lev == "HUMAN_ESCALATION":
                bdr, sym, dtxt = C["magenta"], "\U0001f6a8", "ESCALATED"
            else:
                bdr, sym, dtxt = C["dim"], "\u23f3", "PENDING"

            cf = tk.Frame(self._cards_frame, bg=C["card"],
                          highlightbackground=bdr, highlightthickness=2,
                          highlightcolor=bdr)
            cf.pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=2, expand=True)

            tk.Label(cf, text=f"T{c['tick']:03d} \u2014 {c['sub'].upper()}",
                     bg=C["card"], fg=C["dim"], font=FONT_TINY
                     ).pack(anchor=tk.W, padx=6, pady=(4, 0))
            tk.Label(cf, text=c["ft"].upper().replace("_", " "),
                     bg=C["card"], fg=C["text"],
                     font=(FONT, 9, "bold")).pack(anchor=tk.W, padx=6)
            tk.Label(cf, text=f"{sym} {dtxt}  |  {c['conf']}",
                     bg=C["card"], fg=bdr, font=FONT_TINY
                     ).pack(anchor=tk.W, padx=6, pady=(0, 4))

    # ──────────────────────────────────────────
    # REFRESH: Event Log
    # ──────────────────────────────────────────

    def _refresh_log(self):
        evts = self._events()
        if len(evts) <= self._last_log_idx:
            return
        new = evts[self._last_log_idx:]
        self._last_log_idx = len(evts)

        filt = self._log_filter_var.get()

        self._log.configure(state=tk.NORMAL)
        for e in new:
            et = e.get("event_type", "")
            if et == "SENSOR_DATA":
                continue
            if not self._passes_filter(et, filt):
                continue
            line, tag = self._fmt(et, e.get("tick", 0), e.get("data", {}))
            if line:
                self._log.insert(tk.END, line + "\n", tag)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

        cnt = sum(1 for e in evts if e.get("event_type") != "SENSOR_DATA")
        self._log_cnt.configure(text=str(cnt))

    def _passes_filter(self, et, filt):
        if filt == "ALL":
            return True
        MAP = {
            "FAULTS":    ["FAULT_ISOLATED", "FAULT_INJECTED", "ANOMALY_DETECTED",
                          "TEMPORARY_ANOMALY"],
            "DECISIONS": ["ETHICAL_DECISION"],
            "RECOVERY":  ["RECOVERY_ACTION", "SAFE_MODE"],
            "HUMAN":     ["HUMAN_ESCALATION", "HUMAN_APPROVAL", "OPERATOR_NOTE"],
            "SYSTEM":    ["SYSTEM_START", "SYSTEM_RESET", "SYSTEM_NOMINAL",
                          "SAFE_MODE_EXIT"],
        }
        return et in MAP.get(filt, [])

    def _refilter_log(self):
        """Re-render entire log with new filter."""
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)
        self._last_log_idx = 0

    def _fmt(self, et, tick, d):
        t = f"T{tick:03d}"
        sub = d.get("subsystem", "")
        tag_s = f"[{sub.upper()}] " if sub else ""
        m = {
            "SYSTEM_START":      (f"{t}  \u25cf FDIR System initialized", "system"),
            "SYSTEM_RESET":      (f"{t}  \u25cf System reset to nominal", "system"),
            "SYSTEM_NOMINAL":    (f"{t}  \u2713 System nominal", "nominal"),
            "SAFE_MODE_EXIT":    (f"{t}  \u2713 Safe mode exited by operator", "ok"),
            "FAULT_INJECTED":    (f"{t}  \u25cf {tag_s}FAULT INJECTED: "
                                  f"{d.get('type','?').upper()}", "inject"),
            "TEMPORARY_ANOMALY": (f"{t}  {tag_s}~ Anomaly: "
                                  f"{d.get('temporary_anomalies',[])}", "dim"),
            "ANOMALY_DETECTED":  (f"{t}  {tag_s}\u26a0 ANOMALY: "
                                  f"{d.get('confirmed_anomalies',[])} "
                                  f"[{d.get('overall_status','')}]", "anomaly"),
            "FAULT_ISOLATED":    (f"{t}  {tag_s}\U0001f50d ISOLATED: "
                                  f"{d.get('fault_type','?').upper()} "
                                  f"conf={d.get('confidence_pct','?')}", "isolate"),
            "RECOVERY_ACTION":   (f"{t}  {tag_s}\u2705 RECOVERY: "
                                  f"{d.get('action_taken','?')}", "recover"),
            "HUMAN_ESCALATION":  (f"{t}  \U0001f6a8 HUMAN ESCALATION \u2014 "
                                  f"operator action required", "human"),
            "HUMAN_APPROVAL":    (f"{t}  \U0001f464 APPROVED: "
                                  f"{d.get('fault_type','')} \u2192 "
                                  f"{d.get('approved_action','')}", "nominal"),
            "SAFE_MODE":         (f"{t}  \U0001f6e1 SAFE MODE \u2014 "
                                  f"{str(d.get('reason',''))[:55]}", "safe"),
            "OPERATOR_NOTE":     (f"{t}  \U0001f464 NOTE: {d.get('note','')}", "note"),
        }
        if et == "ETHICAL_DECISION":
            lv = d.get("autonomy_level", "")
            ac = d.get("permitted_action", "")
            conf = d.get("confidence", 0)
            tag = {"FULL_AUTONOMOUS": "dec_full", "LIMITED_ACTION": "dec_lim",
                   "HUMAN_ESCALATION": "dec_hum"}.get(lv, "dim")
            pct = f"{conf:.0%}" if isinstance(conf, float) else str(conf)
            return f"{t}  \u2696 {lv} \u2192 {ac} ({pct})", tag
        return m.get(et, (None, None))

    # ──────────────────────────────────────────
    # REFRESH: Command History
    # ──────────────────────────────────────────

    def _refresh_history(self):
        evts = self._events()
        rows = []
        pending = None
        for e in evts:
            et = e.get("event_type", "")
            d = e.get("data", {})
            tick_val = e.get("tick", 0)
            if et == "FAULT_ISOLATED":
                pending = {
                    "tick": f"T{tick_val:03d}",
                    "sub":  d.get("subsystem", "?").upper(),
                    "ft":   d.get("fault_type", "?"),
                    "conf": d.get("confidence_pct", "?"),
                    "risk": d.get("risk_level", "?"),
                    "dec":  "PENDING", "act": "\u2014", "stat": "PENDING",
                    "tag":  "pending",
                }
            elif et == "ETHICAL_DECISION" and pending:
                lv = d.get("autonomy_level", "?")
                ac = d.get("permitted_action", "none")
                pending["dec"] = lv
                pending["act"] = ac
                if lv == "FULL_AUTONOMOUS":
                    pending["tag"], pending["stat"] = "full", "RESOLVED"
                elif lv == "LIMITED_ACTION":
                    pending["tag"], pending["stat"] = "limited", "RESOLVED"
                elif lv == "HUMAN_ESCALATION":
                    pending["tag"], pending["stat"] = "escalated", "AWAITING"
                rows.append(pending)
                pending = None
            elif et == "HUMAN_APPROVAL":
                # Mark the matching escalated row as resolved
                ft = d.get("fault_type", "")
                for r in reversed(rows):
                    if r["ft"] == ft and r["stat"] == "AWAITING":
                        r["stat"] = "HUMAN OK"
                        r["act"] = d.get("approved_action", r["act"])
                        r["tag"] = "human"
                        break

        self._tree.delete(*self._tree.get_children())
        for r in rows:
            self._tree.insert("", tk.END, values=(
                r["tick"], r["sub"], r["ft"], r["conf"],
                r["risk"], r["dec"], r["act"], r["stat"]),
                tags=(r["tag"],))
        self._hist_cnt.configure(text=str(len(rows)))

    # ──────────────────────────────────────────
    # REFRESH: Charts
    # ──────────────────────────────────────────

    def _refresh_chart(self):
        evts = self._events()
        self._ax.clear()
        self._ax.set_facecolor(C["card"])
        mode = self._chart_mode

        if mode == "bar":
            self._chart_bar(evts)
        elif mode == "pie":
            self._chart_pie(evts)
        elif mode == "hist":
            self._chart_hist(evts)
        elif mode == "trend":
            self._chart_trend()

        try:
            self._fig.tight_layout(pad=1.0)
        except Exception:
            pass
        self._canvas_chart.draw_idle()

    def _style_ax(self):
        ax = self._ax
        ax.tick_params(colors=C["dim"], labelsize=7)
        for sp in ("bottom", "left"):
            ax.spines[sp].set_color(C["border"])
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)

    def _chart_bar(self, evts):
        cnt = Counter()
        for e in evts:
            if e.get("event_type") == "ETHICAL_DECISION":
                cnt[e["data"].get("autonomy_level", "?")] += 1
        labels = ["FULL_AUTO", "LIMITED", "ESCALATED"]
        vals = [cnt.get("FULL_AUTONOMOUS", 0),
                cnt.get("LIMITED_ACTION", 0),
                cnt.get("HUMAN_ESCALATION", 0)]
        cols = [C["green"], C["yellow"], C["magenta"]]
        bars = self._ax.bar(labels, vals, color=cols, width=0.55, edgecolor="none")
        for b, v in zip(bars, vals):
            if v:
                self._ax.text(b.get_x() + b.get_width() / 2,
                              b.get_height() + 0.15, str(v),
                              ha="center", va="bottom",
                              color=C["text"], fontsize=9, fontweight="bold")
        self._ax.set_title("Fault Outcomes", color=C["text"], fontsize=10, pad=8)
        self._ax.set_ylabel("Count", color=C["dim"], fontsize=8)
        self._style_ax()

    def _chart_pie(self, evts):
        cnt = Counter()
        for e in evts:
            if e.get("event_type") == "FAULT_ISOLATED":
                cnt[e["data"].get("fault_type", "?")] += 1
        if cnt:
            labels = list(cnt.keys())
            sizes = list(cnt.values())
            palette = [C["cyan"], C["green"], C["yellow"],
                       C["red"], C["magenta"], C["blue"], C["orange"]]
            colors = palette[:len(labels)]
            self._ax.pie(sizes, labels=None, autopct="%1.0f%%",
                         colors=colors, startangle=90,
                         textprops={"color": C["text"], "fontsize": 8})
            self._ax.legend(labels, loc="center left",
                            bbox_to_anchor=(-0.1, 0.5), fontsize=7,
                            frameon=False, labelcolor=C["text"])
        self._ax.set_title("Fault Distribution", color=C["text"], fontsize=10, pad=8)

    def _chart_hist(self, evts):
        confs = []
        for e in evts:
            if e.get("event_type") == "FAULT_ISOLATED":
                c = e["data"].get("confidence", 0)
                if isinstance(c, (int, float)):
                    confs.append(c * 100 if c <= 1 else c)
        if confs:
            self._ax.hist(confs, bins=10, range=(0, 100),
                          color=C["cyan"], alpha=0.85, edgecolor=C["border"])
        self._ax.set_title("Confidence Distribution", color=C["text"], fontsize=10, pad=8)
        self._ax.set_xlabel("Confidence %", color=C["dim"], fontsize=8)
        self._ax.set_ylabel("Count", color=C["dim"], fontsize=8)
        self._style_ax()

    def _chart_trend(self):
        data = list(self._sensor_history)
        if len(data) > 2:
            tks = [d["tick"] for d in data]
            self._ax.plot(tks, [d["pwr_v"] for d in data],
                          color=C["cyan"], lw=1.3, label="Voltage")
            self._ax.plot(tks, [d["thrm_int"] for d in data],
                          color=C["red"], lw=1.3, label="Int Temp")
            self._ax.plot(tks, [d["pwr_i"] for d in data],
                          color=C["green"], lw=1.0, alpha=0.7, label="Current")
            self._ax.plot(tks, [d["thrm_rad"] for d in data],
                          color=C["yellow"], lw=1.0, alpha=0.7, label="Rad Temp")
            self._ax.legend(fontsize=7, frameon=False, labelcolor=C["text"],
                            loc="upper right")
        self._ax.set_title("Sensor Trends", color=C["text"], fontsize=10, pad=8)
        self._ax.set_xlabel("Tick", color=C["dim"], fontsize=8)
        self._ax.set_ylabel("Value", color=C["dim"], fontsize=8)
        self._style_ax()

    def _switch_chart(self, mode):
        self._chart_mode = mode
        for k, b in self._chart_btns.items():
            b.configure(bg=C["border"] if k == mode else C["card"],
                        fg=C["cyan"] if k == mode else C["dim"])
        self._refresh_chart()

    # ══════════════════════════════════════════
    # COMMAND HANDLERS
    # ══════════════════════════════════════════

    def _cmd_approve_execute(self, fault_type, subsystem, action):
        """Operator approves and executes recovery for a pending fault."""
        main.human_command_queue.put({
            "command":    "approve_and_execute",
            "fault_type": fault_type,
            "subsystem":  subsystem,
            "action":     action,
        })
        self._add_notif(f"\u2714 Approved: {fault_type} \u2192 {action}", "ok")

    def _cmd_dismiss_hold(self, fault_type):
        """Dismiss a human hold without executing recovery (just clears the hold)."""
        if main._ethical_engine:
            main._ethical_engine.clear_human_hold(fault_type)
        self._add_notif(f"\u2716 Dismissed hold: {fault_type}", "warn")

    def _cmd_inject(self):
        sub = self._inj_sub.get()
        ft = self._inj_type.get()
        target = INJECT_DEFAULTS.get(ft, 30.0)
        fc = {"type": ft, "severity": "gradual",
              "description": f"Ground station: inject {ft}",
              "target_value": target}
        q = main.fault_queues.get(sub)
        if q:
            q.put(fc)
        self._add_notif(f"\u26a1 Injected: {ft} on {sub.upper()}", "warn")

    def _cmd_force_action(self):
        sub = self._force_sub.get()
        act = self._force_act.get()
        main.human_command_queue.put({
            "command":   "force_action",
            "subsystem": sub,
            "action":    act,
        })
        self._add_notif(f"\u25b6 Override: {act} on {sub.upper()}", "info")

    def _cmd_phase(self, _event=None):
        p = self._phase_var.get()
        cfg.MISSION_PHASE = p
        with main.state_lock:
            main.system_state["mission_phase"] = p
            main.system_state["mission_criticality"] = \
                cfg.MISSION_PHASE_CRITICALITY.get(p, "LOW")
        self._add_notif(f"\u25cf Phase \u2192 {p}", "info")

    def _cmd_reset(self):
        main.reset_signal.set()
        self._last_log_idx = 0
        self._sensor_history.clear()
        self._prev_card_keys = []
        self._add_notif("\u27f2 System reset sent", "error")

    def _cmd_refresh(self):
        self._tick_counter = 0
        self._add_notif("\u21bb Refreshed", "info")

    def _cmd_exit_safe(self):
        main.human_command_queue.put({"command": "exit_safe_mode"})
        self._add_notif("\u23f9 Exit safe mode sent", "ok")

    def _cmd_annotate(self):
        note = self._note_entry.get().strip()
        if not note:
            return
        main.human_command_queue.put({
            "command": "annotate",
            "note":    note,
        })
        self._note_entry.delete(0, tk.END)
        self._add_notif(f"\U0001f4ac Note sent", "info")

    def _update_inject_types(self, _event=None):
        sub = self._inj_sub.get()
        faults = INJECTABLE_FAULTS.get(sub, [])
        self._inj_cb.configure(values=faults)
        if faults:
            self._inj_type.set(faults[0])

    def _export_log(self):
        """Export current events to a timestamped file."""
        import json, datetime
        fname = f"fdir_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        evts = self._events()
        with open(fname, "w") as f:
            json.dump(evts, f, indent=2, default=str)
        self._add_notif(f"\U0001f4be Exported {len(evts)} events to {fname}", "ok")

    # ══════════════════════════════════════════
    # NOTIFICATIONS
    # ══════════════════════════════════════════

    def _add_notif(self, text, level="info"):
        ts = time.strftime("%H:%M:%S")
        self._notifs.appendleft(f"[{ts}] {text}")
        self._notif_text.configure(state=tk.NORMAL)
        self._notif_text.delete("1.0", tk.END)
        for i, n in enumerate(self._notifs):
            tag = level if i == 0 else "info"
            self._notif_text.insert(tk.END, n + "\n", tag)
        self._notif_text.configure(state=tk.DISABLED)

    # ══════════════════════════════════════════
    # ABOUT POPUP
    # ══════════════════════════════════════════

    def _show_about(self):
        if self._about_win and self._about_win.winfo_exists():
            self._about_win.lift()
            return

        w = tk.Toplevel(self.root)
        w.title("About FDIR System")
        w.geometry("360x460")
        w.configure(bg=C["panel"])
        w.resizable(False, False)
        w.attributes("-topmost", True)
        self._about_win = w

        tk.Label(w, text="\u2726  FDIR SYSTEM  \u2726", bg=C["panel"], fg=C["cyan"],
                 font=(FONT, 16, "bold")).pack(pady=(22, 4))
        tk.Label(w, text="v2.1 \u2014 Interactive Ground Station",
                 bg=C["panel"], fg=C["dim"], font=(FONT, 9)).pack()

        tk.Frame(w, bg=C["border"], height=1).pack(fill=tk.X, padx=30, pady=14)

        info = (
            "Autonomous Fault Detection,\n"
            "Isolation & Recovery System\n\n"
            "Subsystems: POWER, THERMAL\n\n"
            "Pipeline:\n"
            "  Sensor \u2192 Monitor \u2192 Isolate\n"
            "  \u2192 Ethical Gate \u2192 Recovery\n\n"
            "Interactive Features:\n"
            "  \u2022 Human intervention panel\n"
            "  \u2022 Fault injection controls\n"
            "  \u2022 Recovery action overrides\n"
            "  \u2022 Operator annotations\n"
            "  \u2022 Real-time analytics\n"
            "  \u2022 Event log with filtering\n"
            "  \u2022 Safe mode exit commands"
        )
        tk.Label(w, text=info, bg=C["panel"], fg=C["text"],
                 font=(FONT, 9), justify=tk.LEFT).pack(padx=30, pady=4)

        tk.Frame(w, bg=C["border"], height=1).pack(fill=tk.X, padx=30, pady=14)

        tk.Button(w, text="CLOSE", bg=C["card"], fg=C["cyan"],
                  font=(FONT, 9, "bold"), relief=tk.FLAT, padx=22,
                  command=w.destroy, cursor="hand2").pack(pady=(0, 16))

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _events(self):
        try:
            if main._logger:
                return list(main._logger.events)
        except Exception:
            pass
        return []

    def _sep(self, parent):
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X, padx=10, pady=4)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Ensure main module alias for double-import prevention
    if "main" not in sys.modules:
        sys.modules["main"] = main
    app = FDIRDashboard()
    app.run()
