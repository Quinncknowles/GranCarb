#!/usr/bin/env python3
"""
User Input Screen - wxPython recreation of the GAC/Radon calculator input form.

Requires: pip install wxpython
Run:      python3 user_input_screen.py
"""

import wx

YELLOW = wx.Colour(255, 255, 204)
BLUE_TEXT = wx.Colour(0, 0, 200)


class UserInputFrame(wx.Frame):
    def __init__(self):
        super().__init__(
            None,
            title="User input screen",
            size=(520, 620),
        )
        self.SetBackgroundColour(wx.Colour(230, 230, 230))

        self._build_menu()
        self._build_body()

        self.Centre()

    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open...")
        file_menu.Append(wx.ID_SAVE, "&Save...")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit")
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        menubar.Append(file_menu, "&File")

        convert_menu = wx.Menu()
        convert_menu.Append(wx.ID_ANY, "Bq to Ci")
        convert_menu.Append(wx.ID_ANY, "Ci to Bq")
        menubar.Append(convert_menu, "Bq<->Ci")

        protocol_menu = wx.Menu()
        protocol_menu.Append(wx.ID_ANY, "Settings...")
        menubar.Append(protocol_menu, "X-Protocol")

        help_menu = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "&About")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

    # ------------------------------------------------------------------
    def _build_body(self):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        # --- Calculation identifier box -----------------------------------
        id_box = wx.StaticBoxSizer(
            wx.StaticBox(panel, label="Calculation identifier (name, number etc.) :"),
            wx.VERTICAL,
        )
        self.calc_id = wx.TextCtrl(panel, value="Default: No test ID")
        self.calc_id.SetBackgroundColour(YELLOW)
        self.calc_id.SetForegroundColour(BLUE_TEXT)
        font = self.calc_id.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.calc_id.SetFont(font)
        id_box.Add(self.calc_id, 0, wx.EXPAND | wx.ALL, 8)
        outer.Add(id_box, 0, wx.EXPAND | wx.ALL, 10)

        # --- Influent characteristics box -----------------------------------
        inf_box = wx.StaticBoxSizer(
            wx.StaticBox(panel, label="Influent characteristics :"), wx.VERTICAL
        )
        grid = wx.FlexGridSizer(cols=3, vgap=10, hgap=8)
        grid.AddGrowableCol(1, 1)

        grid.Add(
            wx.StaticText(panel, label="Influent activity :"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.influent_activity = wx.TextCtrl(panel)
        self.influent_activity.SetBackgroundColour(YELLOW)
        grid.Add(self.influent_activity, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="pCi/l"), 0, wx.ALIGN_CENTER_VERTICAL)

        grid.Add(
            wx.StaticText(panel, label="Influent volume in gallons or liters :"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        radio_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_gallons = wx.RadioButton(
            panel, label="Gallons", style=wx.RB_GROUP
        )
        self.rb_gallons.SetValue(True)
        self.rb_liters = wx.RadioButton(panel, label="Liters")
        radio_sizer.Add(self.rb_gallons, 0, wx.RIGHT, 15)
        radio_sizer.Add(self.rb_liters, 0)
        grid.Add(radio_sizer, 0)
        grid.Add((0, 0))

        grid.Add(
            wx.StaticText(panel, label="Influent volume :"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.influent_volume = wx.TextCtrl(panel)
        self.influent_volume.SetBackgroundColour(YELLOW)
        grid.Add(self.influent_volume, 1, wx.EXPAND)
        self.volume_unit_label = wx.StaticText(panel, label="Gallons")
        grid.Add(self.volume_unit_label, 0, wx.ALIGN_CENTER_VERTICAL)

        inf_box.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        inf_box.Add(
            wx.StaticText(
                panel, label="Volume generally 50 to 75 gallons per day per person"
            ),
            0,
            wx.ALIGN_CENTER_HORIZONTAL | wx.TOP,
            4,
        )
        outer.Add(inf_box, 0, wx.EXPAND | wx.ALL, 10)

        # Keep the unit label synced with the radio buttons
        self.rb_gallons.Bind(wx.EVT_RADIOBUTTON, self.on_unit_change)
        self.rb_liters.Bind(wx.EVT_RADIOBUTTON, self.on_unit_change)

        # --- GAC filter characteristics box ---------------------------------
        gac_box = wx.StaticBoxSizer(
            wx.StaticBox(panel, label="Granular Activated Carbon filter characteristics"),
            wx.VERTICAL,
        )
        gac_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
        gac_grid.AddGrowableCol(1, 1)

        gac_grid.Add(
            wx.StaticText(panel, label="Radon removal efficiency (percent) :"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.removal_efficiency = wx.TextCtrl(panel)
        self.removal_efficiency.SetBackgroundColour(YELLOW)
        gac_grid.Add(self.removal_efficiency, 1, wx.EXPAND)

        gac_grid.Add((0, 0))
        gac_grid.Add(
            wx.StaticText(panel, label="Generally 90-99 percent"), 0, wx.LEFT, 2
        )

        gac_grid.Add((0, 15))
        gac_grid.Add((0, 15))

        gac_grid.Add(
            wx.StaticText(panel, label="Days operating (1 to X days) :"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.days_operating = wx.TextCtrl(panel)
        self.days_operating.SetBackgroundColour(YELLOW)
        gac_grid.Add(self.days_operating, 1, wx.EXPAND)

        gac_grid.Add((0, 0))
        gac_grid.Add(
            wx.StaticText(
                panel, label="30 days gives greater than 99.5% of equilibrium"
            ),
            0,
            wx.LEFT,
            2,
        )

        gac_box.Add(gac_grid, 0, wx.EXPAND | wx.ALL, 8)
        outer.Add(gac_box, 0, wx.EXPAND | wx.ALL, 10)

        outer.AddStretchSpacer(1)

        # --- Action buttons row 1 -------------------------------------------
        btn_row1 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_waste = wx.Button(panel, label="Waste disposal")
        self.btn_cancer = wx.Button(panel, label="Cancer risks")
        self.btn_gamma = wx.Button(panel, label="Gamma radiation")
        for b in (self.btn_waste, self.btn_cancer, self.btn_gamma):
            btn_row1.Add(b, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # --- Action buttons row 2 -------------------------------------------
        btn_row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_clear = wx.Button(panel, label="Clear")
        self.btn_exit = wx.Button(panel, label="Exit")
        btn_row2.Add(self.btn_clear, 1, wx.EXPAND | wx.ALL, 5)
        btn_row2.Add(self.btn_exit, 1, wx.EXPAND | wx.ALL, 5)
        outer.Add(btn_row2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_exit.Bind(wx.EVT_BUTTON, self.on_exit)

        panel.SetSizer(outer)

    # ------------------------------------------------------------------
    def on_unit_change(self, event):
        unit = "Gallons" if self.rb_gallons.GetValue() else "Liters"
        self.volume_unit_label.SetLabel(unit)

    def on_clear(self, event):
        self.influent_activity.Clear()
        self.influent_volume.Clear()
        self.removal_efficiency.Clear()
        self.days_operating.Clear()

    def on_exit(self, event):
        self.Close()


class App(wx.App):
    def OnInit(self):
        frame = UserInputFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    App().MainLoop()