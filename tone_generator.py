"""
Tone Generator -- accessible wxPython UI.

Run:
    python tone_generator.py

Controls are grouped into a menu bar (File, Playback, Frequency, Settings,
Help). The main window keeps only the controls you reach for constantly:
frequency, preset jump, play/stop, volume.

Ctrl+L, or the Find loudest frequency button, stops any generated tone, records
about three seconds from the chosen listening device on a worker thread, and
sets the frequency control to the loudest spectral component it hears. The
result is announced with a message box; the detected tone is never played
automatically.

Settings -> Listening device chooses what to listen to. Every output device is
offered as a loopback source, which measures what Windows is sending to that
device and needs no microphone; generated tones keep playing while a loopback
is measured, because there has to be something on the output to hear. Below
those come the capture devices: a microphone, line in, a loopback such as
Stereo Mix, or any other device that can capture audio. Settings -> Output
device chooses where the tone is played, so it can go to speakers, headphones,
or another interface. Both choices, and the step sizes from Settings -> Step
sizes..., persist between sessions via wx.Config.
"""

import threading

import wx

from audio_engine import (
    DEFAULT_CAPTURE_SECONDS,
    ToneGenerator,
    detect_loudest_frequency,
    is_loopback_device,
    list_capture_devices,
    list_loopback_devices,
    list_playback_devices,
    record_mono,
)


CONFIG_APP_NAME = "ToneGenerator"
APP_VERSION = "1.0.3"
CFG_SMALL_STEP = "small_step"
CFG_LARGE_STEP = "large_step"
CFG_LISTEN_DEVICE = "listen_device"
CFG_OUTPUT_DEVICE = "output_device"
# Stored for "system default", because wx.Config has no null integer.
DEVICE_SYSTEM_DEFAULT = -1
DEFAULT_SMALL_STEP = 10
DEFAULT_LARGE_STEP = 100
STEP_MIN = 1
STEP_MAX = 10000


class StepConfigDialog(wx.Dialog):
    """Lets the user configure the Ctrl+ and Ctrl+Shift+ step sizes."""

    def __init__(self, parent, small: int, large: int):
        super().__init__(parent, title="Configure step sizes")

        vbox = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(
            self,
            label=(
                "Set how many Hertz the keyboard shortcuts step by.\n"
                "Changes are saved and used every session."
            ),
        )
        vbox.Add(intro, 0, wx.ALL, 10)

        small_label = wx.StaticText(
            self, label="Ctrl + Up / Down step in Hertz:"
        )
        self.small_ctrl = wx.SpinCtrl(
            self, min=STEP_MIN, max=STEP_MAX, initial=small
        )
        self.small_ctrl.SetName("Control Up and Down step size in Hertz")
        vbox.Add(small_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vbox.Add(self.small_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        large_label = wx.StaticText(
            self, label="Ctrl + Shift + Up / Down step in Hertz:"
        )
        self.large_ctrl = wx.SpinCtrl(
            self, min=STEP_MIN, max=STEP_MAX, initial=large
        )
        self.large_ctrl.SetName("Control Shift Up and Down step size in Hertz")
        vbox.Add(large_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vbox.Add(self.large_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btns = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if btns is not None:
            vbox.Add(btns, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizerAndFit(vbox)
        self.small_ctrl.SetFocus()

    def get_values(self) -> tuple[int, int]:
        return self.small_ctrl.GetValue(), self.large_ctrl.GetValue()


class MainFrame(wx.Frame):
    PRESETS = [
        ("20 Hz - sub-bass floor", 20),
        ("60 Hz - mains hum / bass", 60),
        ("100 Hz - low bass", 100),
        ("440 Hz - A4 tuning reference", 440),
        ("1000 Hz - 1 kHz reference", 1000),
        ("3000 Hz - speech clarity", 3000),
        ("8000 Hz - treble", 8000),
        ("12000 Hz - air / cymbals", 12000),
        ("15000 Hz - high-frequency hearing test", 15000),
    ]

    FREQ_MIN = 1
    FREQ_MAX = 24000

    # Static increments that aren't part of the configurable shortcuts.
    FIXED_INCREMENTS = [
        ("-1000 Hz", -1000),
        ("-1 Hz", -1),
        None,
        ("+1 Hz", 1),
        ("+1000 Hz", 1000),
    ]

    def __init__(self):
        super().__init__(None, title="Tone Generator", size=wx.Size(520, 500))
        self.gen = ToneGenerator()
        self._wave_ids: dict[int, str] = {}
        self._chan_ids: dict[int, str] = {}
        self._fixed_ids: dict[int, int] = {}
        self._listen_ids: dict[int, int | None] = {}
        self._output_ids: dict[int, int | None] = {}

        # Menu item handles for the configurable step shortcuts.
        self._small_up_item: wx.MenuItem | None = None
        self._small_down_item: wx.MenuItem | None = None
        self._large_up_item: wx.MenuItem | None = None
        self._large_down_item: wx.MenuItem | None = None
        self._find_item: wx.MenuItem | None = None
        self._hint_text: wx.StaticText | None = None

        # True while a capture is in flight, and once the window is closing so a
        # late worker result is dropped instead of touching dead controls.
        # _measuring_output records whether that capture is a loopback of an
        # output device, which changes both playback and the wording.
        self._listening = False
        self._measuring_output = False
        self._closing = False

        self._load_prefs()
        self._build_menu()
        self._build_ui()
        self._refresh_step_labels()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.play_btn.SetFocus()

    # ---------- prefs ----------
    def _config(self) -> wx.Config:
        return wx.Config(CONFIG_APP_NAME)

    def _load_prefs(self):
        cfg = self._config()
        self.small_step = max(
            STEP_MIN, min(STEP_MAX, cfg.ReadInt(CFG_SMALL_STEP, DEFAULT_SMALL_STEP))
        )
        self.large_step = max(
            STEP_MIN, min(STEP_MAX, cfg.ReadInt(CFG_LARGE_STEP, DEFAULT_LARGE_STEP))
        )
        # Devices are remembered by name, not by index: Windows renumbers them
        # as hardware is plugged in, so an index can quietly point at a
        # different device next session.
        # Output loopbacks are listed first: they measure the output without
        # needing a microphone, and Windows machines with no input device at
        # all report only those.
        self.listen_devices = list_loopback_devices() + list_capture_devices()
        self.playback_devices = list_playback_devices()
        self.listen_label = cfg.Read(CFG_LISTEN_DEVICE, "")
        self.output_label = cfg.Read(CFG_OUTPUT_DEVICE, "")
        self.listen_device = self._index_for(self.listen_label, self.listen_devices)
        self.output_device = self._index_for(self.output_label, self.playback_devices)
        if self.listen_device is None:
            self.listen_label = ""
        if self.output_device is None:
            self.output_label = ""
        self.gen.set_output_device(self.output_device)

    def _save_prefs(self):
        cfg = self._config()
        cfg.WriteInt(CFG_SMALL_STEP, self.small_step)
        cfg.WriteInt(CFG_LARGE_STEP, self.large_step)
        cfg.Write(CFG_LISTEN_DEVICE, self.listen_label)
        cfg.Write(CFG_OUTPUT_DEVICE, self.output_label)
        cfg.Flush()

    @staticmethod
    def _index_for(label: str, devices: list[tuple[int, str]]) -> int | None:
        """Device index for a remembered name, or None for the system default."""
        if not label:
            return None
        for index, name in devices:
            if name == label:
                return index
        return None

    @staticmethod
    def _label_for(device: int | None, devices: list[tuple[int, str]]) -> str:
        for index, label in devices:
            if index == device:
                return label
        return ""

    @classmethod
    def _describe_device(cls, device: int | None, devices: list[tuple[int, str]]) -> str:
        if device is None:
            return "the system default device"
        return cls._label_for(device, devices) or f"device {device}"

    # ---------- menu ----------
    def _build_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q")
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), id=wx.ID_EXIT)
        menubar.Append(file_menu, "&File")

        play_menu = wx.Menu()
        play_id = wx.NewIdRef()
        play_menu.Append(play_id, "&Play / Stop\tF5")
        self.Bind(wx.EVT_MENU, self._on_toggle_play, id=play_id)
        menubar.Append(play_menu, "Pla&yback")

        freq_menu = wx.Menu()
        set_id = wx.NewIdRef()
        freq_menu.Append(set_id, "&Set frequency...\tCtrl+G")
        self.Bind(wx.EVT_MENU, self._on_set_frequency, id=set_id)

        find_id = wx.NewIdRef()
        self._find_item = freq_menu.Append(find_id, "Find &loudest frequency\tCtrl+L")
        self.Bind(wx.EVT_MENU, self._on_find_loudest_frequency, id=find_id)
        freq_menu.AppendSeparator()

        # Configurable-step items. Labels are set by _refresh_step_labels().
        small_up_id = wx.NewIdRef()
        self._small_up_item = freq_menu.Append(small_up_id, "small up placeholder")
        self.Bind(wx.EVT_MENU, lambda _e: self._adjust_freq(self.small_step),
                  id=small_up_id)

        small_down_id = wx.NewIdRef()
        self._small_down_item = freq_menu.Append(small_down_id, "small down placeholder")
        self.Bind(wx.EVT_MENU, lambda _e: self._adjust_freq(-self.small_step),
                  id=small_down_id)

        large_up_id = wx.NewIdRef()
        self._large_up_item = freq_menu.Append(large_up_id, "large up placeholder")
        self.Bind(wx.EVT_MENU, lambda _e: self._adjust_freq(self.large_step),
                  id=large_up_id)

        large_down_id = wx.NewIdRef()
        self._large_down_item = freq_menu.Append(large_down_id, "large down placeholder")
        self.Bind(wx.EVT_MENU, lambda _e: self._adjust_freq(-self.large_step),
                  id=large_down_id)

        freq_menu.AppendSeparator()
        for entry in self.FIXED_INCREMENTS:
            if entry is None:
                freq_menu.AppendSeparator()
                continue
            label, delta = entry
            mid = wx.NewIdRef()
            freq_menu.Append(mid, label)
            self._fixed_ids[int(mid)] = delta
            self.Bind(wx.EVT_MENU, self._on_fixed_delta, id=mid)

        menubar.Append(freq_menu, "&Frequency")

        settings_menu = wx.Menu()
        wave_sub = wx.Menu()
        for name in ToneGenerator.WAVEFORMS:
            mid = wx.NewIdRef()
            item = wave_sub.AppendRadioItem(mid, name)
            self._wave_ids[int(mid)] = name
            if name == self.gen.waveform:
                item.Check(True)
            self.Bind(wx.EVT_MENU, self._on_menu_waveform, id=mid)
        settings_menu.AppendSubMenu(wave_sub, "&Waveform")

        chan_sub = wx.Menu()
        for name in ToneGenerator.CHANNELS:
            mid = wx.NewIdRef()
            item = chan_sub.AppendRadioItem(mid, name)
            self._chan_ids[int(mid)] = name
            if name == self.gen.channel:
                item.Check(True)
            self.Bind(wx.EVT_MENU, self._on_menu_channel, id=mid)
        settings_menu.AppendSubMenu(chan_sub, "Stereo &channel")

        listen_sub = wx.Menu()
        self._fill_device_menu(
            listen_sub,
            self._listen_ids,
            self.listen_devices,
            self.listen_device,
            self._on_menu_listen_device,
            "No capture devices found",
        )
        settings_menu.AppendSubMenu(listen_sub, "&Listening device")

        output_sub = wx.Menu()
        self._fill_device_menu(
            output_sub,
            self._output_ids,
            self.playback_devices,
            self.output_device,
            self._on_menu_output_device,
            "No playback devices found",
        )
        settings_menu.AppendSubMenu(output_sub, "&Output device")

        settings_menu.AppendSeparator()
        steps_id = wx.NewIdRef()
        settings_menu.Append(steps_id, "Step si&zes...\tCtrl+K")
        self.Bind(wx.EVT_MENU, self._on_configure_steps, id=steps_id)
        menubar.Append(settings_menu, "&Settings")

        help_menu = wx.Menu()
        keys_id = wx.NewIdRef()
        help_menu.Append(keys_id, "&Keyboard shortcuts\tF1")
        self.Bind(wx.EVT_MENU, self._on_show_keys, id=keys_id)
        help_menu.Append(wx.ID_ABOUT, "&About")
        self.Bind(wx.EVT_MENU, self._on_about, id=wx.ID_ABOUT)
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

    def _fill_device_menu(self, menu, ids, devices, current, handler, empty_note):
        """Radio list of the system default plus every candidate device."""
        default_id = wx.NewIdRef()
        item = menu.AppendRadioItem(default_id, "System &default")
        ids[int(default_id)] = None
        if current is None:
            item.Check(True)
        self.Bind(wx.EVT_MENU, handler, id=default_id)

        for index, label in devices:
            mid = wx.NewIdRef()
            item = menu.AppendRadioItem(mid, label)
            ids[int(mid)] = index
            if index == current:
                item.Check(True)
            self.Bind(wx.EVT_MENU, handler, id=mid)

        if not devices:
            menu.AppendSeparator()
            note = menu.Append(wx.NewIdRef(), empty_note)
            note.Enable(False)

    def _refresh_step_labels(self):
        """Update menu labels and the main-window hint after step change."""
        if self._small_up_item is not None:
            self._small_up_item.SetItemLabel(
                f"+{self.small_step} Hz\tCtrl+Up"
            )
        if self._small_down_item is not None:
            self._small_down_item.SetItemLabel(
                f"-{self.small_step} Hz\tCtrl+Down"
            )
        if self._large_up_item is not None:
            self._large_up_item.SetItemLabel(
                f"+{self.large_step} Hz\tCtrl+Shift+Up"
            )
        if self._large_down_item is not None:
            self._large_down_item.SetItemLabel(
                f"-{self.large_step} Hz\tCtrl+Shift+Down"
            )
        if self._hint_text is not None:
            self._hint_text.SetLabel(
                f"Up/Down = +/-50 Hz.  "
                f"Ctrl+Up/Down = +/-{self.small_step} Hz.  "
                f"Ctrl+Shift+Up/Down = +/-{self.large_step} Hz.  "
                f"Change step sizes in Settings."
            )
            self._hint_text.Wrap(self.GetClientSize().width - 40)
            self._hint_text.GetContainingSizer().Layout()

    # ---------- main UI ----------
    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        freq_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Frequency")
        row = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(panel, label="&Frequency in Hertz:")
        self.freq_input = wx.SpinCtrlDouble(
            panel, value="1000", min=self.FREQ_MIN, max=self.FREQ_MAX, inc=50
        )
        self.freq_input.SetDigits(0)
        self.freq_input.SetName("Frequency in Hertz, step 50")
        self.freq_input.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_freq_change)
        row.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row.Add(self.freq_input, 1, wx.EXPAND)
        freq_box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        self._hint_text = wx.StaticText(panel, label="")
        freq_box.Add(self._hint_text, 0, wx.ALL, 5)

        self.find_btn = wx.Button(panel, label="Find &loudest frequency (Ctrl+L)")
        self.find_btn.SetName(
            "Find loudest frequency from the listening device, Control L"
        )
        self.find_btn.Bind(wx.EVT_BUTTON, self._on_find_loudest_frequency)
        freq_box.Add(self.find_btn, 0, wx.EXPAND | wx.ALL, 5)

        vbox.Add(freq_box, 0, wx.EXPAND | wx.ALL, 8)

        pre_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Preset frequencies")
        pre_label = wx.StaticText(panel, label="Jump to &preset:")
        self.preset_choice = wx.Choice(panel, choices=[p[0] for p in self.PRESETS])
        self.preset_choice.SetName("Preset frequency selector")
        self.preset_choice.Bind(wx.EVT_CHOICE, self._on_preset)
        pre_box.Add(pre_label, 0, wx.ALL, 3)
        pre_box.Add(self.preset_choice, 0, wx.EXPAND | wx.ALL, 3)
        vbox.Add(pre_box, 0, wx.EXPAND | wx.ALL, 8)

        play_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Playback")
        self.play_btn = wx.Button(panel, label="&Play")
        self.play_btn.SetName("Play tone, toggle button. F5 also toggles.")
        self.play_btn.Bind(wx.EVT_BUTTON, self._on_toggle_play)
        play_box.Add(self.play_btn, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(play_box, 0, wx.EXPAND | wx.ALL, 8)

        vol_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Volume")
        vol_label = wx.StaticText(panel, label="&Volume, 0 to 100 percent:")
        self.vol_slider = wx.Slider(
            panel,
            value=30,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS,
        )
        self.vol_slider.SetName("Volume percent")
        self.vol_slider.Bind(wx.EVT_SLIDER, self._on_volume)
        vol_box.Add(vol_label, 0, wx.ALL, 3)
        vol_box.Add(self.vol_slider, 0, wx.EXPAND | wx.ALL, 3)
        vbox.Add(vol_box, 0, wx.EXPAND | wx.ALL, 8)

        panel.SetSizer(vbox)

        self.CreateStatusBar()
        self.SetStatusText(
            "F5: play/stop.  Up/Down: +/-50 Hz.  Ctrl+G: set frequency.  "
            "Ctrl+L: find loudest frequency.  F1: keys."
        )

    # ---------- handlers ----------
    def _on_freq_change(self, _event):
        self.gen.set_frequency(self.freq_input.GetValue())

    def _on_fixed_delta(self, event):
        delta = self._fixed_ids.get(event.GetId(), 0)
        if delta:
            self._adjust_freq(delta)

    def _adjust_freq(self, delta: int):
        current = self.freq_input.GetValue()
        new_val = max(self.FREQ_MIN, min(self.FREQ_MAX, current + delta))
        self.freq_input.SetValue(new_val)
        self.gen.set_frequency(new_val)
        self.freq_input.SetFocus()
        self.SetStatusText(f"Frequency {new_val:.0f} Hz")

    def _on_set_frequency(self, _event):
        current = int(self.freq_input.GetValue())
        dlg = wx.NumberEntryDialog(
            self,
            f"Enter frequency in Hertz ({self.FREQ_MIN} to {self.FREQ_MAX}):",
            "Hz:",
            "Set frequency",
            current,
            self.FREQ_MIN,
            self.FREQ_MAX,
        )
        if dlg.ShowModal() == wx.ID_OK:
            val = dlg.GetValue()
            self.freq_input.SetValue(val)
            self.gen.set_frequency(val)
            self.SetStatusText(f"Frequency {val} Hz")
        dlg.Destroy()

    def _on_find_loudest_frequency(self, _event):
        if self._listening:
            return
        self._measuring_output = is_loopback_device(self.listen_device)
        if not self._measuring_output:
            # Stop generated audio first: otherwise the listening device hears
            # this window's own tone instead of the sound source being measured.
            self.gen.stop()
            self.play_btn.SetLabel("&Play")
        # A loopback measurement leaves playback alone on purpose: it only
        # hears what the output device is playing, so silence finds nothing,
        # and the tone already running is what gets measured.
        source = self._describe_device(self.listen_device, self.listen_devices)
        seconds = DEFAULT_CAPTURE_SECONDS
        self._set_listening(True)
        if self._measuring_output:
            self.SetStatusText(
                f"Listening to what {source} is playing for {seconds:.0f} seconds..."
            )
        else:
            self.SetStatusText(
                f"Listening to {source} for {seconds:.0f} seconds..."
            )
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _set_listening(self, listening: bool):
        self._listening = listening
        self.find_btn.Enable(not listening)
        if self._find_item is not None:
            self._find_item.Enable(not listening)

    def _listen_worker(self):
        """Capture and analyse off the GUI thread, then hand the result back."""
        result = None
        error = None
        try:
            samples, rate = record_mono(device=self.listen_device)
            result = detect_loudest_frequency(samples, rate)
        except Exception as exc:  # device missing, device busy, driver error
            error = exc
        if not self._closing:
            wx.CallAfter(self._finish_listening, result, error)

    def _finish_listening(self, result, error):
        if self._closing:
            return
        self._set_listening(False)
        source = self._describe_device(self.listen_device, self.listen_devices)

        if error is not None:
            self.SetStatusText("Listening failed")
            wx.MessageBox(
                f"Could not listen on {source}.\n\n"
                f"{error}\n\n"
                "Check the Listening device under the Settings menu, and that "
                "the device is connected and enabled in Windows sound settings.",
                "Listening error",
                wx.OK | wx.ICON_ERROR,
            )
            self.find_btn.SetFocus()
            return

        if result is None:
            self.SetStatusText("No frequency found")
            if self._measuring_output:
                detail = (
                    f"Nothing was audible on {source}. A loopback only hears "
                    "what that output device is playing, so start the tone with "
                    "F5, or play music or a sweep, and try again."
                )
            else:
                detail = (
                    f"No clear frequency was heard on {source}. The recording "
                    "was silent, too quiet, or had no single strong tone.\n\n"
                    "Try a closer source or a louder sound, or check the "
                    "Listening device under the Settings menu."
                )
            wx.MessageBox(
                detail, "No frequency found", wx.OK | wx.ICON_INFORMATION
            )
            self.find_btn.SetFocus()
            return

        hertz = int(round(result))
        self.freq_input.SetValue(hertz)
        self.gen.set_frequency(hertz)
        self.freq_input.SetFocus()
        self.SetStatusText(f"Loudest frequency: {hertz} Hz")
        note = ""
        if self._measuring_output:
            note = (
                "This is the signal Windows sent to that output device, not a "
                "microphone recording, so it shows what system effects and "
                "equalisers did to the tone. Hearing what a speaker or headphone "
                "really produces needs a microphone.\n\n"
            )
        closing = (
            "Playback is still running; press F5 to stop it."
            if self.gen.is_playing
            else "The tone is not playing. Press F5 or the Play button to hear it."
        )
        wx.MessageBox(
            f"Loudest frequency on {source}: {hertz} Hz.\n\n"
            f"{note}"
            f"The frequency control now holds this value. {closing}",
            "Loudest frequency found",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_menu_listen_device(self, event):
        device = self._listen_ids.get(event.GetId())
        self.listen_device = device
        self.listen_label = self._label_for(device, self.listen_devices)
        self._save_prefs()
        self.SetStatusText(
            f"Listening device: {self._describe_device(device, self.listen_devices)}"
        )

    def _on_menu_output_device(self, event):
        device = self._output_ids.get(event.GetId())
        was_playing = self.gen.is_playing
        self.output_device = device
        self.output_label = self._label_for(device, self.playback_devices)
        self.gen.set_output_device(device)
        self._save_prefs()
        description = self._describe_device(device, self.playback_devices)
        if was_playing and self._start_playback():
            self.SetStatusText(f"Output device: {description}. Playing.")
        else:
            self.SetStatusText(f"Output device: {description}")

    def _start_playback(self) -> bool:
        try:
            self.gen.start()
        except Exception as exc:
            wx.MessageBox(
                f"Could not start audio stream:\n{exc}",
                "Audio error",
                wx.OK | wx.ICON_ERROR,
            )
            return False
        self.play_btn.SetLabel("&Stop")
        return True

    def _on_configure_steps(self, _event):
        dlg = StepConfigDialog(self, self.small_step, self.large_step)
        if dlg.ShowModal() == wx.ID_OK:
            self.small_step, self.large_step = dlg.get_values()
            self._save_prefs()
            self._refresh_step_labels()
            self.SetStatusText(
                f"Step sizes: Ctrl +/- {self.small_step} Hz, "
                f"Ctrl+Shift +/- {self.large_step} Hz"
            )
        dlg.Destroy()

    def _on_preset(self, _event):
        idx = self.preset_choice.GetSelection()
        if idx < 0:
            return
        name, freq = self.PRESETS[idx]
        self.freq_input.SetValue(freq)
        self.gen.set_frequency(freq)
        self.SetStatusText(f"Preset: {name}")

    def _on_toggle_play(self, _event):
        if self.gen.is_playing:
            self.gen.stop()
            self.play_btn.SetLabel("&Play")
            self.SetStatusText("Stopped")
        elif self._start_playback():
            self.SetStatusText(
                f"Playing {self.gen.frequency:.0f} Hz "
                f"{self.gen.waveform} on {self.gen.channel}"
            )

    def _on_volume(self, _event):
        vp = self.vol_slider.GetValue()
        self.gen.set_volume(vp / 100.0)
        self.SetStatusText(f"Volume {vp}%")

    def _on_menu_waveform(self, event):
        name = self._wave_ids.get(event.GetId())
        if name:
            self.gen.set_waveform(name)
            self.SetStatusText(f"Waveform: {name}")

    def _on_menu_channel(self, event):
        name = self._chan_ids.get(event.GetId())
        if name:
            self.gen.set_channel(name)
            self.SetStatusText(f"Channel: {name}")

    def _on_show_keys(self, _event):
        msg = (
            "Keyboard shortcuts:\n\n"
            "F5                      Play / Stop\n"
            "Ctrl+G                  Set frequency...\n"
            "Ctrl+L                  Find loudest frequency from the listening device\n"
            "Ctrl+K                  Configure step sizes...\n"
            "Up / Down               +/-50 Hz (frequency field focused)\n"
            f"Ctrl+Up / Ctrl+Down     +/-{self.small_step} Hz (configurable)\n"
            f"Ctrl+Shift+Up / Down    +/-{self.large_step} Hz (configurable)\n"
            "Ctrl+Q                  Exit\n"
            "F1                      This help\n"
            "Alt+F / Y / R / S / H   Open File / Playback / Frequency /\n"
            "                        Settings / Help menus\n"
            "Alt+S then L / O        Choose the Listening or Output device\n"
        )
        wx.MessageBox(msg, "Keyboard shortcuts", wx.OK | wx.ICON_INFORMATION)

    def _on_about(self, _event):
        wx.MessageBox(
            f"Tone Generator {APP_VERSION}\n\n"
            "Accessible audio test-tone generator.\n"
            "Built with wxPython, NumPy, and sounddevice.",
            "About Tone Generator",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_close(self, event):
        self._closing = True
        self.gen.stop()
        event.Skip()


def main():
    app = wx.App()
    frame = MainFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()



