#!/usr/bin/env python3
"""
GAC Radon Removal Calculator - wxPython application.

Screens:
  - User input screen        (main entry screen)
  - Waste disposal screen    (Pb-210 growth curve + pCi/g results)
  - X-Protocol screen        (1-year GAC use, user-defined volume/density)
  - Cancer risks screen      (stub - Non-Functional)
  - Gamma radiation screen   (stub - Non-Functional)
  - Bq <-> Ci calculator     (popup dialog - Non-Functional)

Requires: pip install wxpython 
Run:      python3 GranCarb.py
"""

import webbrowser
import os
import sys
import wx.html2
import wx
from GAC_physics import *
from GAC_theme import *

# ------------------------------------------
#PyInstaller references
#-------------------------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
    
# Centralized Application Resources / Assets
LOGO_PNG_PATH   = resource_path(os.path.join("src", "MooseParty.png"))
APP_ICON_PATH   = resource_path(os.path.join("src", "MooseParty.ico"))
README_MD_PATH  = resource_path("README.md")
    
# ---------------------------------------------------------------------------
# Colors and visual elements -- see GAC_theme.py
# ---------------------------------------------------------------------------    
from GAC_theme import (
YELLOW,
BLUE_TEXT,
GREEN_RESULT,
YELLOW_RESULT,
RED_RESULT
)

# ---------------------------------------------------------------------------
# Physics / unit constants and functions -- see GAC_physics.py
# ---------------------------------------------------------------------------
from GAC_physics import (
    #constants
    PB210_HALFLIFE_YEARS,
    GALLONS_TO_LITERS,
    CUFT_TO_CM3,
    TWO_CUFT_CM3,
    LAYER_VOLUME_FRACTION,
    LAYER_VOLUME_CM3,
    PROGENY_MULTIPLIER,
    CALIBRATION_CONSTANT,
    PCI_PER_G_RED_THRESHOLD,
    PCI_PER_G_YELLOW_THRESHOLD,
    DEFAULT_WET_DENSITY,
    DEFAULT_DRY_DENSITY,
    X_PROTOCOL_YEARS,
    
    #bq ci calc
    BQ_PER_CI,
    M3_TO_LITERS,
    SI_PREFIXES,
    
    #functions
    pb210_growth_fraction,
    total_pb210_pci_at_equilibrium,
    pci_per_gram,
    years_to_reach_threshold
)

#When drawing the graph on Waste disposal screen, determine the color of the dot based on GAC_physics constants
def pci_per_gram_colour(value):
    """Legend colour for a pCi/g reading: red/yellow/green vs thresholds in gac_physics.py."""
    if value > PCI_PER_G_RED_THRESHOLD:
        return RED_RESULT
    elif value > PCI_PER_G_YELLOW_THRESHOLD:
        return YELLOW_RESULT
    return GREEN_RESULT


def safe_float(text_ctrl, default=0.0):
    try:
        return float(text_ctrl.GetValue().strip())
    except (ValueError, AttributeError):
        return default




class BqCiDialog(wx.Frame):
    """Becquerel <---> Curie calculator.

    If I'm honest, I have no idea what the original version of this was meant to do.
    does it just convert values? something else?
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
    
    TODO:
    - Adjust graph x-axis to end at the input number
    """

    ANIMATION_STEP_YEARS = 1   # years revealed per timer tick
    ANIMATION_INTERVAL_MS = 15

    def __init__(self, parent):
        super().__init__(parent, size=(340, 230))
        self.SetBackgroundColour(wx.WHITE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)  # required by wx.AutoBufferedPaintDC
        self.selected_years = 100
        self.total_max_pci = None      # None = nothing calculated yet -> blank
        self.volume_cm3 = None
        self._revealed_up_to = 0
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
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
        return pci_per_gram(total_now, self.volume_cm3)

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

        label_font = gc.CreateFont(
            wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL),
            wx.BLACK,
        )
        gc.SetFont(label_font)

        # gridlines + axis labels
        gc.SetPen(wx.Pen(wx.Colour(180, 180, 180), 1, wx.PENSTYLE_DOT))
        for pct in (0, 25, 50, 75, 100):
            y = py(pct)
            gc.StrokeLine(margin_l, y, margin_l + plot_w, y)
            gc.DrawText(str(pct), 5, y - 6)
        for yr in (0, 25, 50, 75, 100):
            x = px(yr)
            gc.StrokeLine(x, margin_t, x, margin_t + plot_h)
            gc.DrawText(str(yr), x - 8, margin_t + plot_h + 5)

        # axis border
        gc.SetPen(wx.Pen(wx.BLACK, 1))
        gc.StrokeLines([
            (margin_l, margin_t), (margin_l, margin_t + plot_h),
            (margin_l + plot_w, margin_t + plot_h), (margin_l + plot_w, margin_t),
            (margin_l, margin_t),
        ])

        if self.total_max_pci is None:
            italic_font = gc.CreateFont(
                wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL),
                wx.Colour(90, 90, 90),
            )
            gc.SetFont(italic_font)
            gc.DrawText("Press Calculate to generate the growth curve",
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

        # Legend
        legend_sizer = wx.BoxSizer(wx.VERTICAL)
        legend_sizer.Add(self._legend_item("> 2000 pCi/gram", RED_RESULT), 0, wx.BOTTOM, 4)
        legend_sizer.Add(self._legend_item("<= 2000 pCi/gram", YELLOW_RESULT), 0, wx.BOTTOM, 4)
        legend_sizer.Add(self._legend_item("< 1000 pCi/gram", GREEN_RESULT), 0, wx.BOTTOM, 4)
        results_row.Add(legend_sizer, 0, wx.ALL, 8)

        # Graph
        self.graph = GrowthCurvePanel(self)
        results_row.Add(self.graph, 1, wx.EXPAND | wx.ALL, 8)

        results_box.Add(results_row, 0, wx.EXPAND)

        # Numeric readouts grid
        readout_grid = wx.FlexGridSizer(cols=3, vgap=8, hgap=10)
        
        # Row 1: pCi/g Pb-210
        readout_grid.Add(wx.StaticText(self, label="pCi/g Pb-210"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pci_per_g = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_CENTER)
        self.pci_per_g.SetBackgroundColour(GREEN_RESULT)
        readout_grid.Add(self.pci_per_g, 0, wx.EXPAND)
        readout_grid.Add(wx.StaticText(self, label="Wet Weight (density 1.0)"), 0, wx.ALIGN_CENTER_VERTICAL)

        # Row 2: Total Pb-210
        readout_grid.Add(wx.StaticText(self, label="Total Pb-210"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.total_pb210 = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_CENTER)
        self.total_pb210.SetBackgroundColour(YELLOW)
        readout_grid.Add(self.total_pb210, 0, wx.EXPAND)
        readout_grid.Add(wx.StaticText(self, label="pCi"), 0, wx.ALIGN_CENTER_VERTICAL)

        # Row 3: Red Zone Threshold Time (Bottom Right Readout)
        readout_grid.Add(wx.StaticText(self, label="Red zone entry (>2000 pCi/g)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_red_zone_time = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_CENTER)
        self.txt_red_zone_time.SetBackgroundColour(RED_RESULT)
        readout_grid.Add(self.txt_red_zone_time, 0, wx.EXPAND)
        readout_grid.Add(wx.StaticText(self, label="Yr / Mo"), 0, wx.ALIGN_CENTER_VERTICAL)

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
        self.txt_red_zone_time.SetValue("")
        self.pci_per_g.SetBackgroundColour(wx.Colour(230, 230, 230))
        self.pci_per_g.Refresh()
        self.graph.clear()

    def _calculate_red_zone_time(self, total_max_pci, volume_cm3):
        """Formats the year the pCi/g reading crosses the red threshold."""
        years = years_to_reach_threshold(total_max_pci, volume_cm3, PCI_PER_G_RED_THRESHOLD)
        if years is None:
            return "N/A" if not volume_cm3 or total_max_pci <= 0 else "> 100 yrs"
        years_part = int(years)
        months_part = round((years - years_part) * 12)
        if years_part > 0 and months_part > 0:
            return f"{years_part} yrs, {months_part} mos"
        elif years_part > 0:
            return f"{years_part} yrs"
        return f"{months_part} mos"

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
        pci_per_g_wet = pci_per_gram(total_now, volume_cm3)

        self.total_pb210.SetValue(f"{total_now:.2e}")
        self.pci_per_g.SetValue(f"{pci_per_g_wet:.2f}")
        self.pci_per_g.SetBackgroundColour(pci_per_gram_colour(pci_per_g_wet))
        self.pci_per_g.Refresh()

        # Calculate and display time to cross 2000 pCi/g threshold
        red_zone_time = self._calculate_red_zone_time(total_max, volume_cm3)
        self.txt_red_zone_time.SetValue(red_zone_time)

        # Start animation
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
            self,
            min=0.05,
            max=3.0,
            inc=0.01,
            initial=DEFAULT_DRY_DENSITY,
            size=(90, -1),
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
        pb210_1yr = total_max * pb210_growth_fraction(X_PROTOCOL_YEARS)

        volume_cm3 = safe_float(self.user_volume_cm3, default=TWO_CUFT_CM3)
        user_density = self.user_density.GetValue()

        def fill(fields, pci):
            fields[0].SetValue(f"{pci:.3e}")
            fields[1].SetValue(
                f"{(pci / volume_cm3 / DEFAULT_WET_DENSITY):.3f}" if volume_cm3 else "0"
            )
            fields[2].SetValue(
                f"{(pci / volume_cm3 / DEFAULT_DRY_DENSITY):.3f}" if volume_cm3 else "0"
            )
            fields[3].SetValue(
                f"{(pci / volume_cm3 / user_density):.3f}"
                if volume_cm3 and user_density else "0"
            )

        fill(self.pb210_only, pb210_1yr)
        fill(self.pb210_progeny, pb210_1yr * PROGENY_MULTIPLIER)


# ---------------------------------------------------------------------------
#  Gamma Radiation Screen - Tabs located below
# ---------------------------------------------------------------------------
class GammaRadiationPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame

        panel_sizer = wx.BoxSizer(wx.VERTICAL)

        # Notebook Setup
        self.notebook = wx.Notebook(self)
        
        # Instantiate actual tabs
        self.tab_volume = VolumeSourceTab(self.notebook)
        self.tab_point = PointSourceTab(self.notebook)
        self.tab_safe_dist = SafeDistanceTab(self.notebook)

        self.notebook.AddPage(self.tab_volume, "Volume source")
        self.notebook.AddPage(self.tab_point, "Point source")
        self.notebook.AddPage(self.tab_safe_dist, '"Safe distance"')

        panel_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Bottom Navigation Bar
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_user_input = wx.Button(self, label="User input")
        btn_user_input.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.user_input_panel))
        
        btn_cancer_risks = wx.Button(self, label="Cancer risks")
        btn_cancer_risks.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.cancer_risk_panel))

        btn_waste_disposal = wx.Button(self, label="Waste disposal")
        btn_waste_disposal.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.waste_disposal_panel))

        btn_exit = wx.Button(self, label="Exit")
        btn_exit.Bind(wx.EVT_BUTTON, lambda e: frame.Close())

        nav_sizer.Add(btn_user_input, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_cancer_risks, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_waste_disposal, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_exit, 1, wx.LEFT, 5)

        panel_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(panel_sizer)
        

# ---------------------------------------------------------------------------
#  Volume Source tab - Gamma Radiation Screen
# ---------------------------------------------------------------------------
class VolumeSourceTab(wx.Panel):
    """'Volume source' tab matching screenshot reference."""
    def __init__(self, parent):
        super().__init__(parent)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(15)

        # 1. Header Title
        title_lbl = wx.StaticText(self, label="Calculated exposure from a GAC column", style=wx.ALIGN_CENTER)
        f_title = title_lbl.GetFont()
        f_title.SetWeight(wx.FONTWEIGHT_BOLD)
        title_lbl.SetFont(f_title)
        main_sizer.Add(title_lbl, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)

        # 2. Exposure Rate Box (Inset Panel)
        self.box_panel = wx.Panel(self)
        self.box_panel.SetBackgroundColour(wx.Colour(210, 210, 210))  # Muted grey box background
        box_sizer = wx.BoxSizer(wx.VERTICAL)

        # Dynamic calculation display string
        self.calc_text = (
            "The estimated exposure rate 1 meter from the GAC filter wall for a "
            "volume distributed source of 6.94E+07 pCi of radon in equilibrium "
            "with its progeny is: 7.28E-02 mR/hr"
        )
        self.lbl_calc = wx.StaticText(self.box_panel, label=self.calc_text)
        self.lbl_calc.Wrap(450)
        box_sizer.Add(self.lbl_calc, 1, wx.ALL | wx.EXPAND, 12)
        self.box_panel.SetSizer(box_sizer)

        main_sizer.Add(self.box_panel, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 25)
        main_sizer.AddSpacer(25)

        # 3. Instruction Label
        instr_lbl = wx.StaticText(
            self, 
            label="To estimate the probable exposure at other distances, enter the\ndesired distance from the tank wall (greater than 36 inches)"
        )
        main_sizer.Add(instr_lbl, 0, wx.LEFT | wx.RIGHT, 25)
        main_sizer.AddSpacer(10)

        # 4. Input Field
        self.txt_distance = wx.TextCtrl(self, value=">36 inches", size=(140, 25), style=wx.TE_CENTER)
        main_sizer.Add(self.txt_distance, 0, wx.ALIGN_CENTER)

        self.SetSizer(main_sizer)

    def update_values(self, radon_pci="6.94E+07", exposure_rate="7.28E-02"):
        """Call this method to dynamically recalculate the displayed text."""
        updated_text = (
            f"The estimated exposure rate 1 meter from the GAC filter wall for a "
            f"volume distributed source of {radon_pci} pCi of radon in equilibrium "
            f"with its progeny is: {exposure_rate} mR/hr"
        )
        self.lbl_calc.SetLabel(updated_text)
        self.lbl_calc.Wrap(450)
        self.Layout()



# ---------------------------------------------------------------------------
#  Point Source tab - Gamma Radiation Screen
# ---------------------------------------------------------------------------
class PointSourceTab(wx.Panel):
    """'Point source' tab matching screenshot reference."""
    def __init__(self, parent):
        super().__init__(parent)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(15)

        # 1. Header Title
        title_lbl = wx.StaticText(self, label="Calculated exposure from an equivalent point source", style=wx.ALIGN_CENTER)
        f_title = title_lbl.GetFont()
        f_title.SetWeight(wx.FONTWEIGHT_BOLD)
        title_lbl.SetFont(f_title)
        main_sizer.Add(title_lbl, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)

        # 2. Exposure Rate Box (Inset Panel)
        self.box_panel = wx.Panel(self)
        self.box_panel.SetBackgroundColour(wx.Colour(210, 210, 210))  # Muted grey box background
        box_sizer = wx.BoxSizer(wx.VERTICAL)

        self.calc_text = (
            "The estimated exposure rate 1 meter from the GAC filter center line "
            "for a point source of 6.94E+07pCi of radon in equilibrium with its "
            "progeny is: 8.54E-02 mR/hr"
        )
        self.lbl_calc = wx.StaticText(self.box_panel, label=self.calc_text)
        self.lbl_calc.Wrap(450)
        box_sizer.Add(self.lbl_calc, 1, wx.ALL | wx.EXPAND, 12)
        self.box_panel.SetSizer(box_sizer)

        main_sizer.Add(self.box_panel, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 25)
        main_sizer.AddSpacer(25)

        # 3. Instruction Label
        instr_lbl = wx.StaticText(
            self, 
            label="To estimate the probable point source exposure at other distances,\nenter the desired distance from the tank center line (in inches)"
        )
        main_sizer.Add(instr_lbl, 0, wx.LEFT | wx.RIGHT, 25)
        main_sizer.AddSpacer(10)

        # 4. Input Field
        self.txt_distance = wx.TextCtrl(self, size=(140, 25), style=wx.TE_CENTER)
        main_sizer.Add(self.txt_distance, 0, wx.ALIGN_CENTER)

        self.SetSizer(main_sizer)

    def update_values(self, radon_pci="6.94E+07", exposure_rate="8.54E-02"):
        """Call this method to dynamically recalculate the displayed text."""
        updated_text = (
            f"The estimated exposure rate 1 meter from the GAC filter center line "
            f"for a point source of {radon_pci}pCi of radon in equilibrium with its "
            f"progeny is: {exposure_rate} mR/hr"
        )
        self.lbl_calc.SetLabel(updated_text)
        self.lbl_calc.Wrap(450)
        self.Layout()
        
                
# ---------------------------------------------------------------------------
#  Safe Distance tab - Gamma Radiation Screen
# ---------------------------------------------------------------------------
class SafeDistanceTab(wx.Panel):
    """The '"Safe distance"' tab content based on the reference layout."""
    def __init__(self, parent):
        super().__init__(parent)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # -------------------------------------------------------------------
        # Upper Group Box: "Distance considered to have acceptably small risk"
        # -------------------------------------------------------------------
        box = wx.StaticBox(self, label=" Distance considered to have acceptably small risk ")
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        # Main Guideline Text (Bolded like the reference screenshot)
        guideline_text = (
            "Current residential exposure limit guideline based on Carbdose standard of "
            "100 mrem per year for individuals in the general public.  "
            "Distances from tank wall greater than 57.6 inches have probable doses "
            "less than 0.034 mR/hr.  Calculated as a maximum above background for an "
            "8 hr/day exposure, 365 days per year."
        )
        lbl_guideline = wx.StaticText(self, label=guideline_text)
        f_bold = lbl_guideline.GetFont()
        f_bold.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_guideline.SetFont(f_bold)
        lbl_guideline.Wrap(480)  # Wrap to fit inside the panel nicely

        box_sizer.Add(lbl_guideline, 1, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(box_sizer, 0, wx.ALL | wx.EXPAND, 15)

        # Spacer
        main_sizer.AddSpacer(20)

        # -------------------------------------------------------------------
        # Lower Note Section
        # -------------------------------------------------------------------
        note_text = (
            "Note text"
        )
        lbl_note = wx.StaticText(self, label=note_text)
        lbl_note.Wrap(480)

        main_sizer.Add(lbl_note, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 20)

        self.SetSizer(main_sizer)        
        

# ---------------------------------------------------------------------------
#  Cancer Risk Screen - Tabs located below
# ---------------------------------------------------------------------------
class CancerRiskPanel(wx.Panel):
    """Main Cancer Risk Screen matching screenshot layouts."""
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # -------------------------------------------------------------------
        # 1. Top Section: "Choose a cancer risk to present" Group Box
        # -------------------------------------------------------------------
        top_box = wx.StaticBox(self, label=" Choose a cancer risk to present ")
        top_sizer = wx.StaticBoxSizer(top_box, wx.HORIZONTAL)

        # Left Column: Radio Options
        radio_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.rdo_unit = wx.RadioButton(self, label="Unit cancer risk for radon in water", style=wx.RB_GROUP)
        self.rdo_300 = wx.RadioButton(self, label="300 pCi/l MCL water radon cancer risk")
        self.rdo_4000 = wx.RadioButton(self, label="4000 pCi/l AMCL water radon cancer risk")
        self.rdo_untreated = wx.RadioButton(self, label="Your untreated water radon cancer risk")
        self.rdo_treated = wx.RadioButton(self, label="Your treated water radon cancer risk")

        # Set bold blue text for the selected radio button (matching reference)
        f_blue = self.rdo_unit.GetFont()
        f_blue.SetWeight(wx.FONTWEIGHT_BOLD)
        self.rdo_unit.SetFont(f_blue)
        self.rdo_unit.SetForegroundColour(wx.Colour(0, 0, 150))

        radio_sizer.Add(self.rdo_unit, 0, wx.BOTTOM, 2)
        radio_sizer.Add(self.rdo_300, 0, wx.BOTTOM, 2)
        radio_sizer.Add(self.rdo_4000, 0, wx.BOTTOM, 2)
        radio_sizer.Add(self.rdo_untreated, 0, wx.BOTTOM, 2)
        radio_sizer.Add(self.rdo_treated, 0, wx.BOTTOM, 2)

        top_sizer.Add(radio_sizer, 1, wx.ALL, 5)

        # Right Column: Graph Action Buttons
        btn_sizer = wx.BoxSizer(wx.VERTICAL)
        btn_graph_cancers = wx.Button(self, label="Graph cancers", size=(120, -1))
        btn_graph_percent = wx.Button(self, label="Graph percent", size=(120, -1))

        btn_sizer.Add(btn_graph_cancers, 0, wx.BOTTOM, 10)
        btn_sizer.Add(btn_graph_percent, 0)

        top_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        main_sizer.Add(top_sizer, 0, wx.ALL | wx.EXPAND, 8)

        # -------------------------------------------------------------------
        # 2. Middle Section: Notebook Tabs (General / Ever smoker / Never smoker)
        # -------------------------------------------------------------------
        self.notebook = wx.Notebook(self)

        # Mock Data Sets matching screenshots
        general_data = [
            ("Inhalation of radon progeny due to radon released from water", "5.92E-07", "88%"),
            ("Inhalation of radon gas released from water to indoor air", "6.30E-09", "1%"),
            ("Ingestion of radon gas in direct tap water", "7.03E-08", "11%"),
        ]
        general_basis = (
            "0.6 liters of water ingested, occupancy 75 years, 18 hours per day, 1-4 people, "
            "with a water to air transfer ratio of 10,000 to 1. Mixture of ever and never smoking histories."
        )

        smoker_data = [
            ("Inhalation of radon progeny due to radon released from water", "9.59E-07", "92%"),
            ("Inhalation of radon gas released from water to indoor air", "6.30E-09", "1%"),
            ("Ingestion of radon gas in direct tap water", "7.03E-08", "7%"),
        ]
        smoker_basis = (
            "0.6 liters of water ingested, occupancy 75 years, 18 hours per day, 1-4 people, "
            "with a water to air transfer ratio of 10,000 to 1. Ever smoker >= 100 cigarettes in lifetime."
        )

        never_smoker_data = [
            ("Inhalation of radon progeny due to radon released from water", "2.25E-07", "76%"),
            ("Inhalation of radon gas released from water to indoor air", "6.30E-09", "2%"),
            ("Ingestion of radon gas in direct tap water", "7.03E-08", "22%"),
        ]
        never_smoker_basis = (
            "0.6 liters of water ingested, occupancy 75 years, 18 hours per day, 1-4 people, "
            "with a water to air transfer ratio of 10,000 to 1. Never smoker < 100 cigarettes in lifetime."
        )

        # Add Tab Pages
        self.tab_general = PopulationTab(self.notebook, general_data, general_basis)
        self.tab_smoker = PopulationTab(self.notebook, smoker_data, smoker_basis)
        self.tab_never_smoker = PopulationTab(self.notebook, never_smoker_data, never_smoker_basis)

        self.notebook.AddPage(self.tab_general, "General population")
        self.notebook.AddPage(self.tab_smoker, "Ever smoker")
        self.notebook.AddPage(self.tab_never_smoker, "Never smoker")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # -------------------------------------------------------------------
        # 3. Bottom Navigation Bar
        # -------------------------------------------------------------------
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_user_input = wx.Button(self, label="User input")
        btn_user_input.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.user_input_panel))

        btn_gamma = wx.Button(self, label="Gamma radiation")
        btn_gamma.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.gamma_radiation_panel))

        btn_waste = wx.Button(self, label="Waste disposal")
        btn_waste.Bind(wx.EVT_BUTTON, lambda e: frame.show_panel(frame.waste_disposal_panel))

        btn_exit = wx.Button(self, label="Exit")
        btn_exit.Bind(wx.EVT_BUTTON, lambda e: frame.Close())

        nav_sizer.Add(btn_user_input, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_gamma, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_waste, 1, wx.RIGHT, 5)
        nav_sizer.Add(btn_exit, 1, wx.LEFT, 5)

        main_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)        
        

# ---------------------------------------------------------------------------
#  Population tab - Cancer Risk Screen
# ---------------------------------------------------------------------------        
class PopulationTab(wx.Panel):
    """Reusable layout for General population, Ever smoker, and Never smoker tabs."""
    def __init__(self, parent, data, basis_text):
        super().__init__(parent)

        sizer = wx.BoxSizer(wx.VERTICAL)

        # 1. Title Header
        title = wx.StaticText(self, label="Summary of Cancer Risk Estimates")
        f_title = title.GetFont()
        f_title.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(f_title)
        sizer.Add(title, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 8)

        # 2. Main Risk Summary Box
        box = wx.StaticBox(self)
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        # Inner FlexGrid for Tabular Data: [ Pathway Column | Separator Line | Risk Column | Percentage Column ]
        grid = wx.FlexGridSizer(cols=4, vgap=8, hgap=10)
        grid.AddGrowableCol(0, 1)  # Allow description column to take available space

        # Headers
        lbl_h1 = wx.StaticText(self, label="Exposure Pathway")
        lbl_h2 = wx.StaticText(self, label="Lifetime Cancer Risk")
        f_bold = lbl_h1.GetFont()
        f_bold.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_h1.SetFont(f_bold)
        lbl_h2.SetFont(f_bold)

        grid.Add(lbl_h1, 0, wx.LEFT, 5)
        grid.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.EXPAND)
        grid.Add(lbl_h2, 0, wx.ALIGN_LEFT)
        grid.AddSpacer(0)  # Header balance

        # Data Rows
        for pathway, risk, percent in data:
            lbl_path = wx.StaticText(self, label=pathway)
            lbl_risk = wx.StaticText(self, label=risk)
            lbl_pct = wx.StaticText(self, label=f"({percent})")

            lbl_path.Wrap(260)

            grid.Add(lbl_path, 0, wx.LEFT, 5)
            grid.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.EXPAND)
            grid.Add(lbl_risk, 0, wx.ALIGN_LEFT)
            grid.Add(lbl_pct, 0, wx.ALIGN_RIGHT | wx.RIGHT, 10)

        box_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 5)

        # Horizontal Divider Line before "Sum"
        box_sizer.Add(wx.StaticLine(self, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        # Summary / Total Row
        total_grid = wx.FlexGridSizer(cols=4, vgap=5, hgap=10)
        total_grid.AddGrowableCol(0, 1)

        lbl_sum = wx.StaticText(self, label="Sum of all pathways")
        lbl_sum_val = wx.StaticText(self, label=data[-1][1] if data else "0.00")
        lbl_sum_pct = wx.StaticText(self, label="(100%)")

        total_grid.Add(lbl_sum, 0, wx.ALIGN_RIGHT | wx.RIGHT, 15)
        total_grid.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.EXPAND)
        total_grid.Add(lbl_sum_val, 0, wx.ALIGN_LEFT)
        total_grid.Add(lbl_sum_pct, 0, wx.ALIGN_RIGHT | wx.RIGHT, 10)

        box_sizer.Add(total_grid, 0, wx.EXPAND | wx.BOTTOM, 5)
        sizer.Add(box_sizer, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # 3. Basis Text Footer
        lbl_basis = wx.StaticText(self, label=f"Basis: {basis_text}")
        lbl_basis.Wrap(480)
        sizer.Add(lbl_basis, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(sizer)
        
                
# ---------------------------------------------------------------------------
# Stub screens (navigation works, content is a
# placeholder so the app doesn't lose any entered values)
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
                self, label="Screen layout not yet provided - send a reference\n",
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
# Logo Screen - displays logo before continuing to the input page
# ---------------------------------------------------------------------------
class LogoScreen(wx.Panel):
    def __init__(self, parent, frame, image_path=LOGO_PNG_PATH):
        super().__init__(parent)
        self.frame = frame
        self.SetBackgroundColour(wx.Colour(255, 255, 255))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)

        # 1. Logo Display
        if os.path.exists(image_path):
            image = wx.Image(image_path, wx.BITMAP_TYPE_PNG)
            bitmap = wx.StaticBitmap(self, bitmap=wx.Bitmap(image))
            sizer.Add(bitmap, 0, wx.ALIGN_CENTER)
        else:
            placeholder = wx.StaticText(self, label="[ App Logo ]")
            sizer.Add(placeholder, 0, wx.ALIGN_CENTER)

        sizer.AddStretchSpacer(1)

        # 2. Action Buttons (Horizontal Row)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        readme_btn = wx.Button(self, label="View README")
        readme_btn.Bind(wx.EVT_BUTTON, self._on_show_readme)
        btn_sizer.Add(readme_btn, 0, wx.RIGHT, 10)

        continue_btn = wx.Button(self, label="Continue")
        continue_btn.SetDefault()  # Highlights as primary action
        continue_btn.Bind(wx.EVT_BUTTON, self._on_continue)
        btn_sizer.Add(continue_btn, 0, wx.LEFT, 10)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 40)
        self.SetSizer(sizer)

    def _on_continue(self, event):
        self.frame.show_panel(self.frame.user_input_panel)

    def _on_show_readme(self, event):
        dlg = ReadmeDialog(self, readme_path=README_MD_PATH)
        dlg.ShowModal()
        dlg.Destroy()

# ---------------------------------------------------------------------------
# README Screen - displays README.md 
# ---------------------------------------------------------------------------
class ReadmeDialog(wx.Dialog):
    def __init__(self, parent, readme_path=README_MD_PATH):
        super().__init__(parent, title="README Documentation", size=(600, 500),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        content = "README.md not found."
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()

        try:
            import markdown
            html_body = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        except ImportError:
            html_body = f"<pre>{content}</pre>"

        styled_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                       line-height: 1.5; padding: 15px; color: #24292e; background-color: #ffffff; }}
                h1, h2, h3 {{ border-bottom: 1px solid #eaecef; padding-bottom: .3em; }}
                code {{ background-color: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-family: monospace; }}
                pre {{ background-color: #f6f8fa; padding: 10px; border-radius: 6px; overflow: auto; }}
                blockquote {{ border-left: 4px solid #dfe2e5; color: #6a737d; margin: 0; padding-left: 1em; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #dfe2e5; padding: 6px 13px; }}
            </style>
        </head>
        <body>{html_body}</body>
        </html>
        """

        # Scrollable WebView container
        self.browser = wx.html2.WebView.New(self)
        self.browser.SetPage(styled_html, "")
        sizer.Add(self.browser, 1, wx.EXPAND | wx.ALL, 5)

        # Close Button
        close_btn = wx.Button(self, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Centre()

# ---------------------------------------------------------------------------
# Main frame - owns every panel and switches between them
# ---------------------------------------------------------------------------
class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="GAC Radon Removal Calculator", size=(560, 680))
        
        if os.path.exists(APP_ICON_PATH):
            icon = wx.Icon(APP_ICON_PATH, wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)
        self.container = wx.Panel(self)
        self.container_sizer = wx.BoxSizer(wx.VERTICAL)
        self.container.SetSizer(self.container_sizer)

        # Instantiate panels
        self.logo_panel = LogoScreen(self.container, self, LOGO_PNG_PATH)
        self.user_input_panel = UserInputPanel(self.container, self)
        self.waste_disposal_panel = WasteDisposalPanel(self.container, self)
        self.xprotocol_panel = XProtocolPanel(self.container, self)
        self.gamma_radiation_panel = GammaRadiationPanel(self.container, self)
        self.cancer_risk_panel = CancerRiskPanel(self.container, self)

        self.panels = [
            self.logo_panel, self.user_input_panel, self.waste_disposal_panel, 
            self.xprotocol_panel, self.cancer_risk_panel, self.gamma_radiation_panel,
        ]
        for p in self.panels:
            self.container_sizer.Add(p, 1, wx.EXPAND)
            p.Hide()

        self._build_menu()
        
        # Start at the logo screen
        self.show_panel(self.logo_panel)
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