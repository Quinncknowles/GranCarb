#!/usr/bin/env python3
"""
GAC Radon Removal Calculator - wxPython application.

Screens:
  - User input screen        (main entry screen)
  - Waste disposal screen    (Pb-210 growth curve + pCi/g results)
  - X-Protocol screen        (1-year GAC use, user-defined volume/density)
  - Cancer risks screen      (stub - layout not yet provided)
  - Gamma radiation screen   (stub - layout not yet provided)
  - Bq <-> Ci calculator     (popup dialog)

Requires: pip install wxpython
Run:      python3 gac_calculator_app.py

------------------------------------------------------------------------
PHYSICS / MODEL NOTES (read this before trusting the numbers)
------------------------------------------------------------------------
Rn-222 captured on GAC decays through a chain of very short-lived progeny
(Po-218, Pb-214, Bi-214, Po-214 - all well under an hour half-life) down
to Pb-210, which is effectively long-lived (half-life = 22.3 years) by
comparison. So on a "years" timescale, the chain above Pb-210 is treated
as instantaneous, and the interesting slow process is the *ingrowth* of
Pb-210 itself, which follows the standard buildup curve:

    fraction_of_equilibrium(t) = 1 - exp(-lambda_Pb210 * t)
    lambda_Pb210 = ln(2) / 22.3 (per year)

This matches the shape of the reference chart (crosses 50% around the
22-25 year mark = the Pb-210 half-life, and is ~95%+ by 100 years).

Pb-210 itself decays to Bi-210 (t1/2 = 5.01 days) then Po-210
(t1/2 = 138.4 days) then stable Pb-206. Both of those half-lives are
tiny next to a year, so within about a year of Pb-210 being present,
Bi-210 and Po-210 reach *secular equilibrium* with it - meaning their
activities become essentially equal to the Pb-210 activity. That's why
"Growth of Pb-210 plus Bi-210 and Po-210 progeny" is modeled here as
3x the Pb-210-only activity (one full chain of three progeny in
secular equilibrium), not something invented arbitrarily.

The one placeholder assumption is the *volume* used for the "5 inch
layer at top of column" case on the Waste Disposal screen. I don't
have your actual column geometry, so I approximated the top-5-inch
layer as a fraction of a 2 cu ft column (see LAYER_VOLUME_FRACTION
below). Replace that constant once you have the real column dimensions.
------------------------------------------------------------------------
"""

import math
import webbrowser

import wx

# ---------------------------------------------------------------------------
# Shared visual constants
# ---------------------------------------------------------------------------
YELLOW = wx.Colour(255, 255, 204)
BLUE_TEXT = wx.Colour(0, 0, 200)
GREEN_RESULT = wx.Colour(0, 200, 0)
YELLOW_RESULT = wx.Colour(240, 220, 0)
RED_RESULT = wx.Colour(220, 0, 0)

# ---------------------------------------------------------------------------
# Physics / unit constants
# ---------------------------------------------------------------------------
PB210_HALFLIFE_YEARS = 22.3
GALLONS_TO_LITERS = 3.78541
CUFT_TO_CM3 = 28316.846592
TWO_CUFT_CM3 = 2 * CUFT_TO_CM3          # homogeneous-distribution column volume
LAYER_VOLUME_FRACTION = 5.0 / 44.0      # top-5" layer as a fraction of column volume
                                         # (assumes ~44" tall 2 cu ft column - PLACEHOLDER,
                                         #  replace with real geometry when available)
LAYER_VOLUME_CM3 = TWO_CUFT_CM3 * LAYER_VOLUME_FRACTION

PROGENY_MULTIPLIER = 3.0  # Pb-210 + Bi-210 + Po-210 at secular equilibrium

# CALIBRATION_CONSTANT was fit against two known reference outputs from the
# real Waste Disposal screen, both at "Selected time = 100 years" and the
# "5 inch layer" method:
#   activity=900,    12 gal, eff=95%, 30 days -> Total Pb-210 = 2.06E+05 pCi, 31.99 pCi/g
#   activity=120000, 12 gal, eff=90%, 30 days -> Total Pb-210 = 2.60E+07 pCi, 4040.70 pCi/g
# A plain "activity * volume * efficiency * days" formula overshoots both of
# those by a consistent ~5.4x, so this constant divides that out. It is a
# curve fit to match your two examples, NOT derived from a first-principles
# radon/GAC mass-balance model (I don't have your source formula/spec for
# how "days operating" turns into captured activity). If you can share more
# known input/output pairs, or the underlying formula, I can replace this
# with something exact instead of calibrated.
CALIBRATION_CONSTANT = 5.4056


def pb210_growth_fraction(years: float) -> float:
    """Fraction of equilibrium Pb-210 activity reached after `years` of ingrowth."""
    lam = math.log(2) / PB210_HALFLIFE_YEARS
    return 1 - math.exp(-lam * years)


def total_pb210_pci_at_equilibrium(activity_pci_per_l, volume_val, unit,
                                    efficiency_percent, days):
    """
    Total Pb-210 activity (pCi) that will eventually grow in, based on the
    radon activity captured by the GAC bed over the stated operating period.
    See CALIBRATION_CONSTANT above for why this isn't a bare multiplication.
    """
    volume_l = volume_val if unit == "Liters" else volume_val * GALLONS_TO_LITERS
    daily_removed_pci = activity_pci_per_l * volume_l * (efficiency_percent / 100.0)
    return (daily_removed_pci * days) / CALIBRATION_CONSTANT


def pci_per_gram_colour(value):
    """Legend colour for a pCi/g reading: red >2000, yellow 1000-2000, green <1000."""
    if value > 2000:
        return RED_RESULT
    elif value > 1000:
        return YELLOW_RESULT
    return GREEN_RESULT


def safe_float(text_ctrl, default=0.0):
    try:
        return float(text_ctrl.GetValue().strip())
    except (ValueError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Bq <-> Ci popup calculator
# ---------------------------------------------------------------------------
# Metric prefixes available for each unit, mapped to their power-of-ten
# exponent. "(none)" is the base unit (Bq or Ci with no prefix).
SI_PREFIXES = [
    ("p (10^-12)", -12),
    ("n (10^-9)", -9),
    ("u (10^-6)", -6),
    ("m (10^-3)", -3),
    ("(none)", 0),
    ("k (10^3)", 3),
    ("M (10^6)", 6),
    ("G (10^9)", 9),
    ("T (10^12)", 12),
]
BQ_PER_CI = 3.7e10          # exact definition
M3_TO_LITERS = 1000.0       # 1 cubic meter = 1000 liters


class BqCiDialog(wx.Frame):
    """Becquerel <---> Curie calculator.

    Behaves as a normal four-function calculator on the yellow display.
    The Becquerel/Curie radio buttons pick which unit the number on
    display currently represents; switching the radio button converts the
    displayed value on the spot, using whatever prefixes are selected in
    the "Bq Prefix" / "Ci Prefix" dropdowns (e.g. k, m, u...).

    The "Auto xBq/m3 <-> xCi/l" checkbox switches the conversion from a
    plain activity conversion (Bq <-> Ci) to an activity-*concentration*
    conversion (Bq/m3 <-> Ci/l), which brings in the extra factor of 1000
    for the m3-to-liter volume change.

    NOTE: this is a wx.Frame, not a wx.Dialog - wx.Dialog does not support
    SetMenuBar on most platforms (menu bars are a frame-only feature), and
    the reference screenshot has a real File/Options/Help menu bar. It's
    opened non-modally (.Show(), not .ShowModal()) so the user input screen
    stays interactive behind it, same as a real desktop calculator.
    """

    def __init__(self, parent):
        super().__init__(
            parent, title="Becquerel <---> Curie Calculator",
            style=wx.DEFAULT_FRAME_STYLE,
        )
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(230, 230, 230))
        outer = wx.BoxSizer(wx.VERTICAL)

        # --- menu bar -----------------------------------------------------
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit")
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), exit_item)
        menubar.Append(file_menu, "&File")
        options_menu = wx.Menu()
        options_menu.Append(wx.ID_ANY, "Preferences...")
        menubar.Append(options_menu, "&Options")
        help_menu = wx.Menu()
        help_item = help_menu.Append(wx.ID_ABOUT, "&About")
        self.Bind(wx.EVT_MENU, self.on_help, help_item)
        menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)

        # --- Exit button ----------------------------------------------------
        top_row = wx.BoxSizer(wx.HORIZONTAL)
        top_row.AddStretchSpacer(1)
        exit_btn = wx.Button(panel, label="Exit")
        exit_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        top_row.Add(exit_btn, 0)
        outer.Add(top_row, 0, wx.EXPAND | wx.ALL, 8)

        # --- Auto checkbox --------------------------------------------------
        self.auto_check = wx.CheckBox(panel, label="Auto xBq/m3 <-> xCi/l")
        outer.Add(self.auto_check, 0, wx.LEFT | wx.BOTTOM, 10)

        # --- display ----------------------------------------------------
        self.display = wx.TextCtrl(
            panel, value="0.", style=wx.TE_RIGHT | wx.TE_READONLY,
        )
        self.display.SetBackgroundColour(wx.Colour(255, 255, 0))
        disp_font = wx.Font(
            20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        self.display.SetFont(disp_font)
        outer.Add(self.display, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # --- prefix dropdowns + unit radios ---------------------------------
        prefix_row = wx.BoxSizer(wx.HORIZONTAL)

        bq_col = wx.BoxSizer(wx.VERTICAL)
        bq_col.Add(wx.StaticText(panel, label="Bq Prefix"), 0, wx.ALIGN_CENTER_HORIZONTAL)
        self.bq_prefix = wx.ComboBox(
            panel, choices=[p[0] for p in SI_PREFIXES], style=wx.CB_READONLY,
        )
        self.bq_prefix.SetValue("(none)")
        bq_col.Add(self.bq_prefix, 0, wx.EXPAND | wx.TOP, 4)
        self.rb_becquerel = wx.RadioButton(panel, label="Becquerel", style=wx.RB_GROUP)
        self.rb_becquerel.SetValue(True)
        bq_col.Add(self.rb_becquerel, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 6)
        prefix_row.Add(bq_col, 1, wx.EXPAND | wx.RIGHT, 10)

        ci_col = wx.BoxSizer(wx.VERTICAL)
        ci_col.Add(wx.StaticText(panel, label="Ci Prefix"), 0, wx.ALIGN_CENTER_HORIZONTAL)
        self.ci_prefix = wx.ComboBox(
            panel, choices=[p[0] for p in SI_PREFIXES], style=wx.CB_READONLY,
        )
        self.ci_prefix.SetValue("(none)")
        ci_col.Add(self.ci_prefix, 0, wx.EXPAND | wx.TOP, 4)
        self.rb_curie = wx.RadioButton(panel, label="Curie")
        ci_col.Add(self.rb_curie, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 6)
        prefix_row.Add(ci_col, 1, wx.EXPAND)

        outer.Add(prefix_row, 0, wx.EXPAND | wx.ALL, 10)

        self.rb_becquerel.Bind(wx.EVT_RADIOBUTTON, self.on_unit_switch)
        self.rb_curie.Bind(wx.EVT_RADIOBUTTON, self.on_unit_switch)

        # --- keypad -----------------------------------------------------
        keypad = wx.GridBagSizer(vgap=6, hgap=6)
        key_layout = [
            [("7", (0, 0)), ("8", (0, 1)), ("9", (0, 2)), ("C", (0, 3)), ("CE", (0, 4))],
            [("4", (1, 0)), ("5", (1, 1)), ("6", (1, 2)), ("+", (1, 3)), ("-", (1, 4))],
            [("1", (2, 0)), ("2", (2, 1)), ("3", (2, 2)), ("*", (2, 3)), ("/", (2, 4))],
        ]
        for row in key_layout:
            for label, pos in row:
                btn = wx.Button(panel, label=label, size=(48, 36))
                btn.Bind(wx.EVT_BUTTON, self.on_key)
                keypad.Add(btn, pos=pos, flag=wx.EXPAND)

        zero_btn = wx.Button(panel, label="0", size=(48, 36))
        zero_btn.Bind(wx.EVT_BUTTON, self.on_key)
        keypad.Add(zero_btn, pos=(3, 0), span=(1, 2), flag=wx.EXPAND)

        dot_btn = wx.Button(panel, label=".", size=(48, 36))
        dot_btn.Bind(wx.EVT_BUTTON, self.on_key)
        keypad.Add(dot_btn, pos=(3, 2), flag=wx.EXPAND)

        eq_btn = wx.Button(panel, label="=", size=(48, 36))
        eq_btn.Bind(wx.EVT_BUTTON, self.on_key)
        keypad.Add(eq_btn, pos=(3, 3), span=(1, 2), flag=wx.EXPAND)

        for col in range(5):
            keypad.AddGrowableCol(col)

        outer.Add(keypad, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((300, 420))

        # --- calculator state -----------------------------------------------
        self._entry = "0"          # what's currently being typed
        self._stored = None        # left-hand operand waiting on an operator
        self._pending_op = None    # '+', '-', '*', '/'
        self._fresh_entry = True   # next digit starts a new number

    # -----------------------------------------------------------------
    def _prefix_exponent(self, combo):
        label = combo.GetValue()
        for text, exp in SI_PREFIXES:
            if text == label:
                return exp
        return 0

    def _refresh_display(self):
        self.display.SetValue(self._entry)

    def on_key(self, event):
        label = event.GetEventObject().GetLabel()

        if label.isdigit():
            if self._fresh_entry or self._entry == "0":
                self._entry = label
            else:
                self._entry += label
            self._fresh_entry = False

        elif label == ".":
            if self._fresh_entry:
                self._entry = "0."
                self._fresh_entry = False
            elif "." not in self._entry:
                self._entry += "."

        elif label == "C":
            self._entry = "0"
            self._stored = None
            self._pending_op = None
            self._fresh_entry = True

        elif label == "CE":
            self._entry = "0"
            self._fresh_entry = True

        elif label in ("+", "-", "*", "/"):
            self._apply_pending()
            self._stored = float(self._entry)
            self._pending_op = label
            self._fresh_entry = True

        elif label == "=":
            self._apply_pending()
            self._pending_op = None
            self._stored = None
            self._fresh_entry = True

        self._refresh_display()

    def _apply_pending(self):
        if self._pending_op is None or self._stored is None:
            return
        try:
            current = float(self._entry)
        except ValueError:
            current = 0.0
        try:
            if self._pending_op == "+":
                result = self._stored + current
            elif self._pending_op == "-":
                result = self._stored - current
            elif self._pending_op == "*":
                result = self._stored * current
            elif self._pending_op == "/":
                result = self._stored / current if current != 0 else 0.0
            else:
                result = current
        except ZeroDivisionError:
            result = 0.0
        self._entry = f"{result:g}"

    # -----------------------------------------------------------------
    def on_unit_switch(self, event):
        """Convert the displayed value when the Becquerel/Curie radio changes."""
        try:
            value = float(self._entry)
        except ValueError:
            return

        bq_exp = self._prefix_exponent(self.bq_prefix)
        ci_exp = self._prefix_exponent(self.ci_prefix)
        volume_factor = M3_TO_LITERS if self.auto_check.GetValue() else 1.0

        if self.rb_curie.GetValue():
            # value was entered in Bq (with bq_exp prefix) -> convert to Ci (with ci_exp prefix)
            bq_value = value * (10 ** bq_exp)
            ci_value = (bq_value / BQ_PER_CI) * volume_factor
            result = ci_value / (10 ** ci_exp)
        else:
            # value was entered in Ci (with ci_exp prefix) -> convert to Bq (with bq_exp prefix)
            ci_value = value * (10 ** ci_exp)
            bq_value = (ci_value * BQ_PER_CI) / volume_factor
            result = bq_value / (10 ** bq_exp)

        self._entry = f"{result:g}"
        self._fresh_entry = True
        self._refresh_display()

    def on_help(self, event):
        wx.MessageBox(
            "Type a number on the keypad, then choose Becquerel or Curie to "
            "set what unit it's in. Switching between Becquerel and Curie "
            "converts the number using the selected Bq/Ci prefixes.\n\n"
            "Check 'Auto xBq/m3 <-> xCi/l' to convert activity "
            "*concentrations* (per cubic meter vs. per liter) instead of "
            "plain activity.",
            "About this calculator", wx.OK | wx.ICON_INFORMATION,
        )


# ---------------------------------------------------------------------------
# User input screen
# ---------------------------------------------------------------------------
class UserInputPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self.SetBackgroundColour(wx.Colour(230, 230, 230))
        outer = wx.BoxSizer(wx.VERTICAL)

        id_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Calculation identifier (name, number etc.) :"),
            wx.VERTICAL,
        )
        self.calc_id = wx.TextCtrl(self, value="Default: No test ID")
        self.calc_id.SetBackgroundColour(YELLOW)
        self.calc_id.SetForegroundColour(BLUE_TEXT)
        font = self.calc_id.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.calc_id.SetFont(font)
        id_box.Add(self.calc_id, 0, wx.EXPAND | wx.ALL, 8)
        outer.Add(id_box, 0, wx.EXPAND | wx.ALL, 10)

        inf_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Influent characteristics :"), wx.VERTICAL
        )
        grid = wx.FlexGridSizer(cols=3, vgap=10, hgap=8)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="Influent activity :"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.influent_activity = wx.TextCtrl(self)
        self.influent_activity.SetBackgroundColour(YELLOW)
        grid.Add(self.influent_activity, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label="pCi/l"), 0, wx.ALIGN_CENTER_VERTICAL)

        grid.Add(
            wx.StaticText(self, label="Influent volume in gallons or liters :"),
            0, wx.ALIGN_CENTER_VERTICAL,
        )
        radio_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_gallons = wx.RadioButton(self, label="Gallons", style=wx.RB_GROUP)
        self.rb_gallons.SetValue(True)
        self.rb_liters = wx.RadioButton(self, label="Liters")
        radio_sizer.Add(self.rb_gallons, 0, wx.RIGHT, 15)
        radio_sizer.Add(self.rb_liters, 0)
        grid.Add(radio_sizer, 0)
        grid.Add((0, 0))

        grid.Add(wx.StaticText(self, label="Influent volume :"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.influent_volume = wx.TextCtrl(self)
        self.influent_volume.SetBackgroundColour(YELLOW)
        grid.Add(self.influent_volume, 1, wx.EXPAND)
        self.volume_unit_label = wx.StaticText(self, label="Gallons")
        grid.Add(self.volume_unit_label, 0, wx.ALIGN_CENTER_VERTICAL)

        inf_box.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        inf_box.Add(
            wx.StaticText(self, label="Volume generally 50 to 75 gallons per day per person"),
            0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 4,
        )
        outer.Add(inf_box, 0, wx.EXPAND | wx.ALL, 10)

        self.rb_gallons.Bind(wx.EVT_RADIOBUTTON, self.on_unit_change)
        self.rb_liters.Bind(wx.EVT_RADIOBUTTON, self.on_unit_change)

        gac_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Granular Activated Carbon filter characteristics"),
            wx.VERTICAL,
        )
        gac_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
        gac_grid.AddGrowableCol(1, 1)

        gac_grid.Add(
            wx.StaticText(self, label="Radon removal efficiency (percent) :"),
            0, wx.ALIGN_CENTER_VERTICAL,
        )
        self.removal_efficiency = wx.TextCtrl(self)
        self.removal_efficiency.SetBackgroundColour(YELLOW)
        gac_grid.Add(self.removal_efficiency, 1, wx.EXPAND)

        gac_grid.Add((0, 0))
        gac_grid.Add(wx.StaticText(self, label="Generally 90-99 percent"), 0, wx.LEFT, 2)

        gac_grid.Add((0, 15))
        gac_grid.Add((0, 15))

        gac_grid.Add(
            wx.StaticText(self, label="Days operating (1 to X days) :"),
            0, wx.ALIGN_CENTER_VERTICAL,
        )
        self.days_operating = wx.TextCtrl(self)
        self.days_operating.SetBackgroundColour(YELLOW)
        gac_grid.Add(self.days_operating, 1, wx.EXPAND)

        gac_grid.Add((0, 0))
        gac_grid.Add(
            wx.StaticText(self, label="30 days gives greater than 99.5% of equilibrium"),
            0, wx.LEFT, 2,
        )

        gac_box.Add(gac_grid, 0, wx.EXPAND | wx.ALL, 8)
        outer.Add(gac_box, 0, wx.EXPAND | wx.ALL, 10)

        outer.AddStretchSpacer(1)

        btn_row1 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_waste = wx.Button(self, label="Waste disposal")
        self.btn_cancer = wx.Button(self, label="Cancer risks")
        self.btn_gamma = wx.Button(self, label="Gamma radiation")
        for b in (self.btn_waste, self.btn_cancer, self.btn_gamma):
            btn_row1.Add(b, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_clear = wx.Button(self, label="Clear")
        self.btn_exit = wx.Button(self, label="Exit")
        btn_row2.Add(self.btn_clear, 1, wx.EXPAND | wx.ALL, 5)
        btn_row2.Add(self.btn_exit, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_waste.Bind(wx.EVT_BUTTON, self.on_waste_disposal)
        self.btn_cancer.Bind(wx.EVT_BUTTON, self.on_cancer_risks)
        self.btn_gamma.Bind(wx.EVT_BUTTON, self.on_gamma_radiation)
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_exit.Bind(wx.EVT_BUTTON, self.on_exit)

        self.SetSizer(outer)

    def get_volume_unit(self):
        return "Gallons" if self.rb_gallons.GetValue() else "Liters"

    def on_unit_change(self, event):
        self.volume_unit_label.SetLabel(self.get_volume_unit())

    def on_waste_disposal(self, event):
        self.frame.show_panel(self.frame.waste_disposal_panel)

    def on_cancer_risks(self, event):
        self.frame.show_panel(self.frame.cancer_risk_panel)

    def on_gamma_radiation(self, event):
        self.frame.show_panel(self.frame.gamma_radiation_panel)

    def on_clear(self, event):
        self.influent_activity.Clear()
        self.influent_volume.Clear()
        self.removal_efficiency.Clear()
        self.days_operating.Clear()

    def on_exit(self, event):
        self.frame.Close()


# ---------------------------------------------------------------------------
# Custom-drawn growth curve control used on the Waste Disposal screen
# ---------------------------------------------------------------------------
class GrowthCurvePanel(wx.Panel):
    """Plots % of Pb-210 equilibrium vs. years (0-100).

    Stays blank until run() is called (i.e. until Calculate is pressed).
    Once run, the curve animates in year-by-year, and each plotted point is
    colored by its own pCi/g reading at that point in time (green/yellow/red
    per the same thresholds as the legend) rather than one fixed color -
    matching how the reference screenshots show curves that start green and
    can shade into yellow/red as the years (and activity) build up.
    """

    ANIMATION_STEP_YEARS = 2   # years revealed per timer tick
    ANIMATION_INTERVAL_MS = 15

    def __init__(self, parent):
        super().__init__(parent, size=(340, 230))
        self.SetBackgroundColour(wx.WHITE)
        self.selected_years = 100
        self.total_max_pci = None      # None = nothing calculated yet -> blank
        self.volume_cm3 = None
        self._revealed_up_to = 0
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def run(self, total_max_pci, volume_cm3, selected_years):
        """Kick off (or restart) the animated draw for a fresh Calculate press."""
        self.total_max_pci = total_max_pci
        self.volume_cm3 = volume_cm3
        self.selected_years = max(1, min(100, selected_years))
        self._revealed_up_to = 0
        self.timer.Stop()
        self.timer.Start(self.ANIMATION_INTERVAL_MS)

    def clear(self):
        self.timer.Stop()
        self.total_max_pci = None
        self.volume_cm3 = None
        self._revealed_up_to = 0
        self.Refresh()

    def on_timer(self, event):
        self._revealed_up_to = min(100, self._revealed_up_to + self.ANIMATION_STEP_YEARS)
        self.Refresh()
        if self._revealed_up_to >= 100:
            self.timer.Stop()

    def _pci_per_gram_at(self, years):
        if not self.volume_cm3:
            return 0.0
        total_now = self.total_max_pci * pb210_growth_fraction(years)
        return total_now / self.volume_cm3

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return

        w, h = self.GetClientSize()
        margin_l, margin_r, margin_t, margin_b = 45, 15, 15, 35
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        def px(years):
            return margin_l + (years / 100.0) * plot_w

        def py(percent):
            return margin_t + plot_h - (percent / 100.0) * plot_h

        # gridlines + axis labels
        gc.SetPen(wx.Pen(wx.Colour(180, 180, 180), 1, wx.PENSTYLE_DOT))
        dc.SetTextForeground(wx.BLACK)
        dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        for pct in (0, 25, 50, 75, 100):
            y = py(pct)
            gc.StrokeLine(margin_l, y, margin_l + plot_w, y)
            dc.DrawText(str(pct), 5, y - 6)
        for yr in (0, 25, 50, 75, 100):
            x = px(yr)
            gc.StrokeLine(x, margin_t, x, margin_t + plot_h)
            dc.DrawText(str(yr), x - 8, margin_t + plot_h + 5)

        # axis border
        gc.SetPen(wx.Pen(wx.BLACK, 1))
        gc.StrokeLines([
            (margin_l, margin_t), (margin_l, margin_t + plot_h),
            (margin_l + plot_w, margin_t + plot_h), (margin_l + plot_w, margin_t),
            (margin_l, margin_t),
        ])

        if self.total_max_pci is None:
            dc.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
            dc.DrawText("Press Calculate to generate the growth curve",
                        margin_l + 15, margin_t + plot_h / 2 - 8)
            return

        # the growth curve, drawn as small dots colored by their own pCi/g
        # reading (matches how the reference curves shade from green into
        # yellow/red as activity builds up over the years)
        gc.SetPen(wx.TRANSPARENT_PEN)
        for yr in range(0, self._revealed_up_to + 1):
            pct = pb210_growth_fraction(yr) * 100.0
            colour = pci_per_gram_colour(self._pci_per_gram_at(yr))
            gc.SetBrush(wx.Brush(colour))
            x, y = px(yr), py(pct)
            gc.DrawEllipse(x - 1.5, y - 1.5, 3, 3)

        # dashed guide lines at the selected year
        sel_pct = pb210_growth_fraction(self.selected_years) * 100.0
        gc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 1, wx.PENSTYLE_SHORT_DASH))
        gc.StrokeLine(px(self.selected_years), margin_t + plot_h,
                      px(self.selected_years), py(sel_pct))
        gc.StrokeLine(margin_l, py(sel_pct), px(self.selected_years), py(sel_pct))


# ---------------------------------------------------------------------------
# Waste disposal screen
# ---------------------------------------------------------------------------
class WasteDisposalPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self.SetBackgroundColour(wx.Colour(230, 230, 230))
        outer = wx.BoxSizer(wx.VERTICAL)

        # --- Calculation method box -----------------------------------
        method_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Calculation method"), wx.VERTICAL
        )
        self.rb_layer = wx.RadioButton(
            self, label="Radioactivity assigned to 5 inch layer at top of a cylindrical GAC column",
            style=wx.RB_GROUP,
        )
        self.rb_layer.SetValue(True)
        self.rb_homogeneous = wx.RadioButton(
            self, label="Radioactivity homogeniously distributed in a 2 cu.ft. cylindrical GAC column",
        )
        method_box.Add(self.rb_layer, 0, wx.ALL, 5)
        method_box.Add(self.rb_homogeneous, 0, wx.ALL, 5)

        time_row = wx.BoxSizer(wx.HORIZONTAL)
        self.selected_time = wx.TextCtrl(self, value="100", size=(60, -1))
        self.selected_time.SetBackgroundColour(YELLOW)
        time_row.Add(self.selected_time, 0, wx.RIGHT, 8)
        time_row.Add(
            wx.StaticText(self, label="Selected time in years (1-100)"),
            0, wx.ALIGN_CENTER_VERTICAL,
        )
        method_box.Add(time_row, 0, wx.ALL, 5)
        outer.Add(method_box, 0, wx.EXPAND | wx.ALL, 10)

        # --- Calculation results box -----------------------------------
        results_box = wx.StaticBoxSizer(
            wx.StaticBox(self, label="Calculation results"), wx.VERTICAL
        )
        results_row = wx.BoxSizer(wx.HORIZONTAL)

        # legend
        legend_sizer = wx.BoxSizer(wx.VERTICAL)
        legend_sizer.Add(self._legend_item("> 2000 pCi/gram", RED_RESULT), 0, wx.BOTTOM, 4)
        legend_sizer.Add(self._legend_item("<= 2000 pCi/gram", YELLOW_RESULT), 0, wx.BOTTOM, 4)
        legend_sizer.Add(self._legend_item("< 1000 pCi/gram", GREEN_RESULT), 0, wx.BOTTOM, 4)
        results_row.Add(legend_sizer, 0, wx.ALL, 8)

        # graph
        self.graph = GrowthCurvePanel(self)
        results_row.Add(self.graph, 1, wx.EXPAND | wx.ALL, 8)

        results_box.Add(results_row, 0, wx.EXPAND)

        # numeric readouts
        readout_grid = wx.FlexGridSizer(cols=3, vgap=8, hgap=10)
        readout_grid.Add(wx.StaticText(self, label="pCi/g Pb-210"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pci_per_g = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_CENTER)
        self.pci_per_g.SetBackgroundColour(GREEN_RESULT)
        readout_grid.Add(self.pci_per_g, 0, wx.EXPAND)
        readout_grid.Add(wx.StaticText(self, label="Wet Weight (density 1.0)"), 0, wx.ALIGN_CENTER_VERTICAL)

        readout_grid.Add(wx.StaticText(self, label="Total Pb-210"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.total_pb210 = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_CENTER)
        self.total_pb210.SetBackgroundColour(YELLOW)
        readout_grid.Add(self.total_pb210, 0, wx.EXPAND)
        readout_grid.Add(wx.StaticText(self, label="pCi"), 0, wx.ALIGN_CENTER_VERTICAL)

        results_box.Add(readout_grid, 0, wx.ALL, 10)

        self.caption = wx.StaticText(
            self, label="100 Years Growth of Progeny on GAC from Radon Removal\n"
                         "Vs. Percent Radioactive Equilibrium",
            style=wx.ALIGN_CENTER,
        )
        results_box.Add(self.caption, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        outer.Add(results_box, 1, wx.EXPAND | wx.ALL, 10)

        # --- Bottom buttons -----------------------------------
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_user_input = wx.Button(self, label="User input")
        self.btn_cancer = wx.Button(self, label="Cancer risks")
        self.btn_calculate = wx.Button(self, label="Calculate")
        self.btn_gamma = wx.Button(self, label="Gamma radiation")
        self.btn_exit = wx.Button(self, label="Exit")
        for b in (self.btn_user_input, self.btn_cancer, self.btn_calculate,
                  self.btn_gamma, self.btn_exit):
            btn_row.Add(b, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_user_input.Bind(wx.EVT_BUTTON, self.on_back)
        self.btn_cancer.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.cancer_risk_panel))
        self.btn_calculate.Bind(wx.EVT_BUTTON, self.on_calculate)
        self.btn_gamma.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.gamma_radiation_panel))
        self.btn_exit.Bind(wx.EVT_BUTTON, lambda e: frame.Close())

        self.SetSizer(outer)
        self._show_placeholder_readouts()

    def _legend_item(self, text, colour):
        row = wx.BoxSizer(wx.HORIZONTAL)
        swatch = wx.Panel(self, size=(14, 14))
        swatch.SetBackgroundColour(colour)
        row.Add(swatch, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(wx.StaticText(self, label=text), 0, wx.ALIGN_CENTER_VERTICAL)
        return row

    def _show_placeholder_readouts(self):
        """Blank state before Calculate has been pressed."""
        self.total_pb210.SetValue("")
        self.pci_per_g.SetValue("")
        self.pci_per_g.SetBackgroundColour(wx.Colour(230, 230, 230))
        self.pci_per_g.Refresh()
        self.graph.clear()

    def on_back(self, event):
        self.frame.show_panel(self.frame.user_input_panel)

    def on_calculate(self, event):
        uip = self.frame.user_input_panel
        activity = safe_float(uip.influent_activity)
        volume = safe_float(uip.influent_volume)
        unit = uip.get_volume_unit()
        efficiency = safe_float(uip.removal_efficiency, default=95.0)
        days = safe_float(uip.days_operating, default=30.0)

        try:
            years = float(self.selected_time.GetValue().strip())
        except ValueError:
            years = 100.0
        years = max(1.0, min(100.0, years))

        total_max = total_pb210_pci_at_equilibrium(activity, volume, unit, efficiency, days)
        total_now = total_max * pb210_growth_fraction(years)

        volume_cm3 = LAYER_VOLUME_CM3 if self.rb_layer.GetValue() else TWO_CUFT_CM3
        pci_per_g_wet = total_now / volume_cm3 if volume_cm3 else 0.0

        self.total_pb210.SetValue(f"{total_now:.2e}")
        self.pci_per_g.SetValue(f"{pci_per_g_wet:.2f}")
        self.pci_per_g.SetBackgroundColour(pci_per_gram_colour(pci_per_g_wet))
        self.pci_per_g.Refresh()

        # curve only appears (and animates in) once Calculate is pressed
        self.graph.run(total_max, volume_cm3, years)


# ---------------------------------------------------------------------------
# X-Protocol screen
# ---------------------------------------------------------------------------
class XProtocolPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self.SetBackgroundColour(wx.Colour(230, 230, 230))
        outer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(
            self, label="X-Protocol: 1 year GAC use with user\ndefined volume and density",
            style=wx.ALIGN_CENTER,
        )
        title_font = title.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 2)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        outer.Add(title, 0, wx.ALIGN_CENTER | wx.ALL, 12)

        top_grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        top_grid.AddGrowableCol(0, 0)

        self.user_volume_cm3 = wx.TextCtrl(self, value=str(int(TWO_CUFT_CM3)), size=(120, -1))
        self.user_volume_cm3.SetBackgroundColour(YELLOW)
        top_grid.Add(self.user_volume_cm3, 0)
        top_grid.Add(
            wx.StaticText(self, label="User defined volume in cubic centimeters (used for all calculations)"),
            0, wx.ALIGN_CENTER_VERTICAL,
        )

        density_row = wx.BoxSizer(wx.HORIZONTAL)
        self.user_density = wx.SpinCtrlDouble(
            self, min=0.05, max=3.0, inc=0.01, initial=0.45, size=(90, -1)
        )
        self.user_density.SetDigits(2)
        density_row.Add(self.user_density, 0)
        top_grid.Add(density_row, 0)
        top_grid.Add(
            wx.StaticText(self, label="User defined density"), 0, wx.ALIGN_CENTER_VERTICAL,
        )

        outer.Add(top_grid, 0, wx.ALL, 15)

        self.pb210_only = self._results_box(
            outer, "Growth of Pb-210 only",
            ["pCi activity after 1 year of filter use",
             "pCi/g Wet GAC after 1 year of filter use (density = 1.00)",
             "pCi/g Dry GAC after 1 year of filter use (density = 0.45)",
             "pCi/g GAC after 1 year of filter use (density user defined)"],
        )
        self.pb210_progeny = self._results_box(
            outer, "Growth of Pb-210 plus Bi-210 and Po-210 progeny",
            ["pCi activity after 1 year of filter use",
             "pCi/g Wet GAC after 1 year of filter use (density = 1.00)",
             "pCi/g Dry GAC after 1 year of filter use (density = 0.45)",
             "pCi/g GAC after 1 year of filter use (density user defined)"],
        )

        outer.AddStretchSpacer(1)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_calculate = wx.Button(self, label="Calculate")
        self.btn_back = wx.Button(self, label="Back")
        self.btn_clear = wx.Button(self, label="Clear")
        self.btn_bqci = wx.Button(self, label="Bq<->Ci")
        self.btn_help = wx.Button(self, label="Help")
        for b in (self.btn_calculate, self.btn_back, self.btn_clear, self.btn_bqci, self.btn_help):
            btn_row.Add(b, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_calculate.Bind(wx.EVT_BUTTON, self.on_calculate)
        self.btn_back.Bind(wx.EVT_BUTTON, self.on_back)
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_bqci.Bind(wx.EVT_BUTTON, self.on_bqci)
        self.btn_help.Bind(wx.EVT_BUTTON, self.on_help)

        self.SetSizer(outer)

    def _results_box(self, outer, title, labels):
        box = wx.StaticBoxSizer(wx.StaticBox(self, label=title), wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        fields = []
        for label in labels:
            field = wx.TextCtrl(self, style=wx.TE_READONLY, size=(120, -1))
            field.SetBackgroundColour(YELLOW)
            grid.Add(field, 0)
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            fields.append(field)
        box.Add(grid, 0, wx.ALL, 8)
        outer.Add(box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        return fields

    def on_back(self, event):
        self.frame.show_panel(self.frame.user_input_panel)

    def on_clear(self, event):
        for field in self.pb210_only + self.pb210_progeny:
            field.SetValue("")

    def on_bqci(self, event):
        BqCiDialog(self.frame).Show()

    def on_help(self, event):
        wx.MessageBox(
            "Enter a GAC volume (cm3) and a density, then press Calculate.\n\n"
            "Pb-210 activity is modeled from the influent activity, volume, "
            "removal efficiency and days operating entered on the User input "
            "screen, run for 1 year of continuous filter use. The 'plus "
            "progeny' figures assume Bi-210 and Po-210 have reached secular "
            "equilibrium with Pb-210 (valid after roughly a year of ingrowth).",
            "X-Protocol Help", wx.OK | wx.ICON_INFORMATION,
        )

    def on_calculate(self, event):
        uip = self.frame.user_input_panel
        activity = safe_float(uip.influent_activity)
        volume = safe_float(uip.influent_volume)
        unit = uip.get_volume_unit()
        efficiency = safe_float(uip.removal_efficiency, default=95.0)
        days = safe_float(uip.days_operating, default=30.0)

        total_max = total_pb210_pci_at_equilibrium(activity, volume, unit, efficiency, days)
        pb210_1yr = total_max * pb210_growth_fraction(1.0)

        volume_cm3 = safe_float(self.user_volume_cm3, default=TWO_CUFT_CM3)
        user_density = self.user_density.GetValue()

        def fill(fields, pci):
            fields[0].SetValue(f"{pci:.3e}")
            fields[1].SetValue(f"{(pci / volume_cm3 / 1.00):.3f}" if volume_cm3 else "0")
            fields[2].SetValue(f"{(pci / volume_cm3 / 0.45):.3f}" if volume_cm3 else "0")
            fields[3].SetValue(
                f"{(pci / volume_cm3 / user_density):.3f}" if volume_cm3 and user_density else "0"
            )

        fill(self.pb210_only, pb210_1yr)
        fill(self.pb210_progeny, pb210_1yr * PROGENY_MULTIPLIER)


# ---------------------------------------------------------------------------
# Stub screens (layout not yet provided - navigation works, content is a
# placeholder so the app doesn't lose any entered values when you visit them)
# ---------------------------------------------------------------------------
class StubPanel(wx.Panel):
    def __init__(self, parent, frame, title):
        super().__init__(parent)
        self.frame = frame
        self.SetBackgroundColour(wx.Colour(230, 230, 230))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddStretchSpacer(1)

        heading = wx.StaticText(self, label=title, style=wx.ALIGN_CENTER)
        f = heading.GetFont()
        f.SetPointSize(f.GetPointSize() + 3)
        f.SetWeight(wx.FONTWEIGHT_BOLD)
        heading.SetFont(f)
        outer.Add(heading, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        outer.Add(
            wx.StaticText(
                self, label="Screen layout not yet provided - send a reference\n"
                             "screenshot and I'll build this one out too.",
                style=wx.ALIGN_CENTER,
            ),
            0, wx.ALIGN_CENTER,
        )
        outer.AddStretchSpacer(1)

        back_btn = wx.Button(self, label="Back to User input")
        back_btn.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.user_input_panel))
        outer.Add(back_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)

        self.SetSizer(outer)


# ---------------------------------------------------------------------------
# Main frame - owns every panel and switches between them
# ---------------------------------------------------------------------------
class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="GAC Radon Removal Calculator", size=(560, 680))

        self.container = wx.Panel(self)
        self.container_sizer = wx.BoxSizer(wx.VERTICAL)
        self.container.SetSizer(self.container_sizer)

        self.user_input_panel = UserInputPanel(self.container, self)
        self.waste_disposal_panel = WasteDisposalPanel(self.container, self)
        self.xprotocol_panel = XProtocolPanel(self.container, self)
        self.cancer_risk_panel = StubPanel(self.container, self, "Cancer risks screen")
        self.gamma_radiation_panel = StubPanel(self.container, self, "Gamma radiation screen")

        self.panels = [
            self.user_input_panel, self.waste_disposal_panel, self.xprotocol_panel,
            self.cancer_risk_panel, self.gamma_radiation_panel,
        ]
        for p in self.panels:
            self.container_sizer.Add(p, 1, wx.EXPAND)
            p.Hide()

        self._build_menu()
        self.show_panel(self.user_input_panel)
        self.Centre()

    # -----------------------------------------------------------------
    def _build_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        print_item = file_menu.Append(wx.ID_ANY, "Print All Current Values")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit")
        self.Bind(wx.EVT_MENU, self.on_print_values, print_item)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), exit_item)
        menubar.Append(file_menu, "&File")

        bqci_menu = wx.Menu()
        bqci_item = bqci_menu.Append(wx.ID_ANY, "Open Bq<->Ci Calculator")
        self.Bind(wx.EVT_MENU, self.on_open_bqci, bqci_item)
        menubar.Append(bqci_menu, "Bq<->Ci")

        protocol_menu = wx.Menu()
        protocol_item = protocol_menu.Append(wx.ID_ANY, "Go to X-Protocol Screen")
        self.Bind(wx.EVT_MENU, lambda e: self.show_panel(self.xprotocol_panel), protocol_item)
        menubar.Append(protocol_menu, "X-Protocol")

        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About")
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

    # -----------------------------------------------------------------
    def show_panel(self, panel):
        for p in self.panels:
            p.Hide()
        panel.Show()
        self.container_sizer.Layout()
        self.Layout()

    def on_open_bqci(self, event):
        BqCiDialog(self).Show()

    def on_about(self, event):
        webbrowser.open("https://github.com/Quinncknowles/GranCarb/blob/main/README.md")

    def on_print_values(self, event):
        uip = self.user_input_panel
        wdp = self.waste_disposal_panel
        lines = [
            f"Calculation identifier: {uip.calc_id.GetValue()}",
            f"Influent activity: {uip.influent_activity.GetValue()} pCi/l",
            f"Influent volume: {uip.influent_volume.GetValue()} {uip.get_volume_unit()}",
            f"Removal efficiency: {uip.removal_efficiency.GetValue()} %",
            f"Days operating: {uip.days_operating.GetValue()}",
            "",
            f"Waste disposal - Total Pb-210: {wdp.total_pb210.GetValue()} pCi",
            f"Waste disposal - pCi/g Pb-210 (wet): {wdp.pci_per_g.GetValue()}",
        ]
        wx.MessageBox("\n".join(lines), "Current Values", wx.OK | wx.ICON_INFORMATION)


class App(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    App().MainLoop()