"""Dark, tray-aware GUI for Dota 2 Auto Accept."""

import os
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image

import autostart
import config
import telegram_notifier as tg
from engine import AutoAcceptEngine
from engine_events import EngineEvent, EngineState
from tray import HAS_TRAY, TrayIcon
from ui_state import display_for

BOT_USERNAME = "DotaAutoAccept_bot"


APP_TITLE = "Dota 2 Auto Accept"
WINDOW_W, WINDOW_H = 500, 700
FONT_BODY_SIZE = 12
FONT_CAPTION_SIZE = 11

C_BG = "#0D0F13"
C_SURFACE = "#171A20"
C_SURFACE_ALT = "#20242C"
C_BORDER = "#2B303A"
C_TEXT = "#F4F6F8"
C_MUTED = "#99A2AE"
C_RED = "#D94141"
C_RED_HOVER = "#B83232"
C_RED_SOFT = "#3A1D21"
C_GREEN = "#35C66A"
C_GREEN_HOVER = "#279B55"
C_GREEN_SOFT = "#163523"
C_WORK = "#F0A43A"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _resource(name):
    return config.resource_path(os.path.join("images", name))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.resizable(False, False)
        self.configure(fg_color=C_BG)

        self.cfg = config.load()
        if (
            not self.cfg.get("focus_mode_configured", False)
            or not self.cfg.get("switch_focus", True)
        ):
            self.cfg["switch_focus"] = True
            self.cfg["focus_mode_configured"] = True
            config.save(self.cfg)

        self.engine = None
        self.engine_thread = None
        self._engine_active = False
        self._engine_generation = 0
        self.tray = None
        self._last_event = EngineEvent(
            EngineState.STOPPED,
            "Остановлен",
            "Нажмите «Старт» для мониторинга",
        )

        self._set_window_icon()
        self._build_ui()
        self._apply_config()
        self._apply_engine_event(self._last_event)

        if HAS_TRAY:
            self.tray = TrayIcon(self._show_window, self._real_quit)
            self.tray.start()

        tg.start_background_listener(self._on_chat_id)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.cfg.get("start_minimized", False) and HAS_TRAY:
            self.after(120, self.withdraw)

    def _set_window_icon(self):
        ico = _resource("logo.ico")
        if os.path.isfile(ico):
            try:
                self.iconbitmap(default=ico)
            except Exception:
                pass
        png = _resource("logo_48.png")
        self._tk_icon = None
        if os.path.isfile(png):
            try:
                self._tk_icon = tk.PhotoImage(file=png)
                self.iconphoto(True, self._tk_icon)
            except Exception:
                pass

    def _build_ui(self):
        self._build_header()

        self.page_host = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self.page_host.pack(fill="both", expand=True, padx=16, pady=(10, 4))
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)
        self._pages = {}

        self._build_home()
        self._build_telegram()
        self._build_settings()
        self._build_navigation()
        self._show_page("Главная")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=C_SURFACE, corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        accent = ctk.CTkFrame(header, width=4, fg_color=C_RED, corner_radius=0)
        accent.pack(side="left", fill="y")

        self._logo = None
        logo_path = _resource("logo_64.png")
        if os.path.isfile(logo_path):
            self._logo = ctk.CTkImage(Image.open(logo_path), size=(44, 44))

        ctk.CTkLabel(
            header,
            image=self._logo,
            text="" if self._logo else "✓",
            width=46,
        ).pack(side="left", padx=(14, 10), pady=12)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", pady=12)
        ctk.CTkLabel(
            title_box,
            text=APP_TITLE,
            font=("Segoe UI", 18, "bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="BACKGROUND READY CHECK",
            font=("Segoe UI", FONT_CAPTION_SIZE, "bold"),
            text_color=C_MUTED,
        ).pack(anchor="w")

        self.lbl_header_state = ctk.CTkLabel(
            header,
            text="● Остановлен",
            font=("Segoe UI", FONT_BODY_SIZE, "bold"),
            text_color=C_MUTED,
        )
        self.lbl_header_state.pack(side="right", padx=16)

    def _build_navigation(self):
        nav = ctk.CTkFrame(
            self,
            fg_color=C_SURFACE,
            border_width=1,
            border_color=C_BORDER,
            corner_radius=14,
        )
        nav.pack(fill="x", padx=16, pady=(0, 10))

        self._nav_buttons = {}
        names = ("Главная", "Telegram", "Настройки")
        for column, name in enumerate(names):
            nav.grid_columnconfigure(column, weight=1, uniform="navigation")
            button = ctk.CTkButton(
                nav,
                text=name,
                width=90,
                height=40,
                corner_radius=10,
                fg_color="transparent",
                hover_color=C_SURFACE_ALT,
                text_color=C_MUTED,
                font=("Segoe UI", FONT_BODY_SIZE, "bold"),
                command=lambda page=name: self._show_page(page),
            )
            button.grid(row=0, column=column, sticky="ew", padx=3, pady=3)
            self._nav_buttons[name] = button

    def _page(self, name, scroll=False):
        if scroll:
            page = ctk.CTkScrollableFrame(
                self.page_host,
                fg_color="transparent",
                corner_radius=0,
                scrollbar_button_color=C_RED,
                scrollbar_button_hover_color=C_RED_HOVER,
            )
        else:
            page = ctk.CTkFrame(self.page_host, fg_color="transparent", corner_radius=0)
        page.grid(row=0, column=0, sticky="nsew")
        self._pages[name] = page
        return page

    def _card(self, parent, **kwargs):
        return ctk.CTkFrame(
            parent,
            fg_color=kwargs.pop("fg_color", C_SURFACE),
            border_width=1,
            border_color=kwargs.pop("border_color", C_BORDER),
            corner_radius=16,
            **kwargs,
        )

    def _section_title(self, parent, title, subtitle=""):
        ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI", 25, "bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                parent,
                text=subtitle,
                font=("Segoe UI", FONT_BODY_SIZE),
                text_color=C_MUTED,
            ).pack(anchor="w", pady=(1, 10))

    def _build_home(self):
        page = self._page("Главная")

        intro = self._card(page, fg_color=C_SURFACE_ALT)
        intro.pack(fill="x")
        ctk.CTkLabel(
            intro,
            text="Автопринятие матчей Dota 2",
            font=("Segoe UI", 15, "bold"),
            text_color=C_TEXT,
        ).pack(anchor="w", padx=16, pady=(13, 2))
        self.lbl_home_description = ctk.CTkLabel(
            intro,
            text=(
                "Приложение ждёт сигнал Dota, проверяет кнопку принятия, "
                "выводит игру вперёд и нажимает Enter."
            ),
            font=("Segoe UI", FONT_BODY_SIZE),
            text_color=C_MUTED,
            justify="left",
            wraplength=420,
        )
        self.lbl_home_description.pack(anchor="w", padx=16, pady=(0, 13))

        status = self._card(page, border_color="#343A45")
        status.pack(fill="x", pady=(8, 0))

        top_line = ctk.CTkFrame(status, height=3, fg_color=C_RED, corner_radius=3)
        top_line.pack(fill="x", padx=18, pady=(16, 0))

        self.status_orb = ctk.CTkLabel(
            status,
            image=self._logo,
            text="" if self._logo else "✓",
            width=92,
            height=92,
            fg_color=C_SURFACE_ALT,
            corner_radius=46,
        )
        self.status_orb.pack(pady=(14, 6))

        self.lbl_status = ctk.CTkLabel(
            status,
            text="Остановлен",
            font=("Segoe UI", 28, "bold"),
            text_color=C_TEXT,
        )
        self.lbl_status.pack()

        self.lbl_detail = ctk.CTkLabel(
            status,
            text="",
            font=("Segoe UI", FONT_BODY_SIZE),
            text_color=C_MUTED,
            wraplength=400,
        )
        self.lbl_detail.pack(padx=22, pady=(2, 12))

        self.btn_toggle = ctk.CTkButton(
            status,
            text="Старт",
            height=50,
            corner_radius=12,
            font=("Segoe UI", 15, "bold"),
            fg_color=C_GREEN,
            hover_color=C_GREEN_HOVER,
            text_color="white",
            command=self._toggle_engine,
        )
        self.btn_toggle.pack(fill="x", padx=18, pady=(0, 10))

        self.lbl_focus_mode = ctk.CTkLabel(
            status,
            text="✓  Перед Enter Dota всегда выводится на передний план",
            font=("Segoe UI", FONT_CAPTION_SIZE, "bold"),
            text_color=C_GREEN,
        )
        self.lbl_focus_mode.pack(pady=(0, 12))

        latest = self._card(page)
        latest.pack(fill="x", pady=(8, 0))
        heading = ctk.CTkFrame(latest, fg_color="transparent")
        heading.pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            heading,
            text="ПОСЛЕДНЕЕ СОБЫТИЕ",
            font=("Segoe UI", FONT_CAPTION_SIZE, "bold"),
            text_color=C_MUTED,
        ).pack(side="left")
        ctk.CTkLabel(
            heading,
            text="LIVE",
            width=42,
            height=20,
            corner_radius=10,
            fg_color=C_RED_SOFT,
            text_color="#FF7A7A",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

        self.lbl_latest = ctk.CTkLabel(
            latest,
            text="Приложение готово",
            font=("Segoe UI", 15, "bold"),
            text_color=C_TEXT,
        )
        self.lbl_latest.pack(anchor="w", padx=16)
        self.lbl_latest_detail = ctk.CTkLabel(
            latest,
            text="",
            font=("Segoe UI", FONT_BODY_SIZE),
            text_color=C_MUTED,
            wraplength=420,
        )
        self.lbl_latest_detail.pack(anchor="w", padx=16, pady=(3, 14))

    def _build_telegram(self):
        page = self._page("Telegram", scroll=True)
        self._section_title(page, "Telegram", "Уведомления о принятой игре")

        # ── Quick link card ──
        link_card = self._card(page)
        link_card.pack(fill="x", pady=(0, 12))
        self._card_heading(
            link_card,
            "БЫСТРАЯ ПРИВЯЗКА",
            "Нажмите кнопку — Telegram откроется автоматически",
        )

        self.btn_link_telegram = ctk.CTkButton(
            link_card,
            text="  Привязать Telegram  ",
            height=48,
            corner_radius=12,
            fg_color=C_GREEN,
            hover_color=C_GREEN_HOVER,
            text_color="white",
            font=("Segoe UI", 14, "bold"),
            command=self._link_telegram,
        )
        self.btn_link_telegram.pack(fill="x", padx=16, pady=(0, 8))

        mini_guide = ctk.CTkLabel(
            link_card,
            text=(
                "Нажмите кнопку выше — откроется Telegram.\n"
                "Chat ID привяжется автоматически.\n"
                "Если нет — введите /start"
            ),
            justify="left",
            font=("Segoe UI", FONT_CAPTION_SIZE),
            text_color=C_MUTED,
        )
        mini_guide.pack(anchor="w", padx=16, pady=(0, 14))

        self.lbl_link_status = ctk.CTkLabel(
            link_card, text="", text_color=C_MUTED, wraplength=400,
            font=("Segoe UI", FONT_BODY_SIZE, "bold"),
        )
        self.lbl_link_status.pack(padx=16, pady=(0, 14))

        # ── Notifications card ──
        card = self._card(page)
        card.pack(fill="x")

        self.var_tg = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            card,
            text="Включить уведомления",
            variable=self.var_tg,
            progress_color=C_RED,
            button_color=C_TEXT,
            text_color=C_TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 10))

        ctk.CTkLabel(
            card,
            text="CHAT ID",
            text_color=C_MUTED,
            font=("Segoe UI", FONT_CAPTION_SIZE, "bold"),
        ).pack(anchor="w", padx=16)
        self.ent_chat = ctk.CTkEntry(
            card,
            placeholder_text="Telegram Chat ID",
            height=44,
            fg_color=C_SURFACE_ALT,
            border_color=C_BORDER,
            text_color=C_TEXT,
        )
        self.ent_chat.pack(fill="x", padx=16, pady=(5, 10))
        ctk.CTkButton(
            card,
            text="Проверить подключение",
            height=42,
            fg_color=C_RED,
            hover_color=C_RED_HOVER,
            command=self._test_telegram,
        ).pack(fill="x", padx=16, pady=(0, 10))
        self.lbl_tg = ctk.CTkLabel(card, text="", text_color=C_MUTED, wraplength=400)
        self.lbl_tg.pack(padx=16, pady=(0, 14))

    def _build_settings(self):
        page = self._page("Настройки", scroll=True)
        self._section_title(page, "Настройки", "Обнаружение и поведение приложения")

        self.var_color = ctk.BooleanVar(value=True)
        self.var_template = ctk.BooleanVar(value=True)
        self.var_enter = ctk.BooleanVar(value=True)
        self.var_exit = ctk.BooleanVar(value=False)
        self.var_start_minimized = ctk.BooleanVar(value=False)
        self.var_autostart = ctk.BooleanVar(value=False)
        self._slider_meta = {}

        detection = self._card(page)
        detection.pack(fill="x", pady=(0, 12))
        self._card_heading(
            detection,
            "ОБНАРУЖЕНИЕ",
            "Три независимых метода — можно включить один, несколько или все",
        )
        self.lbl_color_method_help = self._setting_switch(
            detection,
            "Цветовое распознавание",
            "Быстрый метод: ищет зелёную кнопку по цвету и работает на любом разрешении.",
            self.var_color,
        )
        self.lbl_template_method_help = self._setting_switch(
            detection,
            "Распознавание по шаблону",
            "Точный метод: сравнивает экран с эталонным изображением кнопки принятия.",
            self.var_template,
        )
        self.lbl_signal_method_help = self._setting_switch(
            detection,
            "Резервный Enter по сигналу",
            (
                "Резерв по системному сигналу: если распознавание не помогло, "
                "после мигания Dota или перехода в её окно программа "
                "сфокусирует игру и нажмёт Enter."
            ),
            self.var_enter,
        )
        self.sld_threshold = self._setting_slider(
            detection,
            "Порог совпадения",
            "threshold",
            0.30,
            1.00,
            70,
            lambda value: f"{value:.2f}",
        )
        self.sld_scan = self._setting_slider(
            detection,
            "Интервал страховочного скана",
            "scan",
            0.0,
            10.0,
            20,
            lambda value: "выкл." if value < 0.25 else f"{value:.1f} с",
        )
        self.sld_retry = self._setting_slider(
            detection,
            "Время поиска после события",
            "retry",
            1.0,
            15.0,
            14,
            lambda value: f"{value:.0f} с",
        )
        self.sld_debounce = self._setting_slider(
            detection,
            "Защита от повторного принятия",
            "debounce",
            2.0,
            30.0,
            28,
            lambda value: f"{value:.0f} с",
        )

        behavior = self._card(page)
        behavior.pack(fill="x", pady=(0, 12))
        self._card_heading(
            behavior,
            "ПОВЕДЕНИЕ",
            "Мониторинг всё равно запускается только кнопкой «Старт»",
        )
        self._setting_switch(
            behavior,
            "Остановить после принятия",
            "Завершить мониторинг после успешного Enter",
            self.var_exit,
        )
        self._setting_switch(
            behavior,
            "Запускать окно свёрнутым",
            "Открывать в трее без автоматического старта",
            self.var_start_minimized,
        )
        self._setting_switch(
            behavior,
            "Автозагрузка Windows",
            "Запускать приложение при входе в систему",
            self.var_autostart,
        )

        self.btn_save_settings = ctk.CTkButton(
            page,
            text="Сохранить настройки",
            height=46,
            corner_radius=12,
            fg_color=C_RED,
            hover_color=C_RED_HOVER,
            text_color="white",
            font=("Segoe UI", 14, "bold"),
            command=self._save_settings,
        )
        self.btn_save_settings.pack(fill="x")
        self.lbl_settings_status = ctk.CTkLabel(
            page,
            text="",
            text_color=C_MUTED,
            font=("Segoe UI", FONT_CAPTION_SIZE),
        )
        self.lbl_settings_status.pack(pady=(5, 12))

    def _card_heading(self, parent, title, subtitle):
        ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI", 12, "bold"),
            text_color="#FF7373",
        ).pack(anchor="w", padx=16, pady=(15, 0))
        ctk.CTkLabel(
            parent,
            text=subtitle,
            font=("Segoe UI", FONT_CAPTION_SIZE),
            text_color=C_MUTED,
            wraplength=400,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(2, 8))

    def _setting_switch(self, parent, title, subtitle, variable):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=6)
        text_box = ctk.CTkFrame(row, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_box,
            text=title,
            font=("Segoe UI", 13, "bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")
        subtitle_label = ctk.CTkLabel(
            text_box,
            text=subtitle,
            font=("Segoe UI", FONT_CAPTION_SIZE),
            text_color=C_MUTED,
            justify="left",
            wraplength=320,
        )
        subtitle_label.pack(anchor="w")
        ctk.CTkSwitch(
            row,
            text="",
            width=44,
            variable=variable,
            progress_color=C_RED,
            button_color=C_TEXT,
            button_hover_color="white",
        ).pack(side="right", padx=(10, 0))
        return subtitle_label

    def _setting_slider(self, parent, title, key, from_, to, steps, formatter):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.pack(fill="x", padx=16, pady=7)
        heading = ctk.CTkFrame(block, fg_color="transparent")
        heading.pack(fill="x")
        ctk.CTkLabel(
            heading,
            text=title,
            font=("Segoe UI", 12, "bold"),
            text_color=C_TEXT,
        ).pack(side="left")
        value_label = ctk.CTkLabel(
            heading,
            text=formatter(from_),
            width=62,
            height=22,
            corner_radius=8,
            fg_color=C_SURFACE_ALT,
            text_color=C_TEXT,
            font=("Segoe UI", FONT_CAPTION_SIZE, "bold"),
        )
        value_label.pack(side="right")
        slider = ctk.CTkSlider(
            block,
            from_=from_,
            to=to,
            number_of_steps=steps,
            height=16,
            fg_color=C_SURFACE_ALT,
            progress_color=C_RED,
            button_color=C_TEXT,
            button_hover_color="#FFFFFF",
            command=lambda value, label=value_label, fmt=formatter: label.configure(
                text=fmt(value)
            ),
        )
        slider.pack(fill="x", pady=(5, 2))
        self._slider_meta[key] = (slider, value_label, formatter)
        return slider

    def _set_slider(self, key, value):
        slider, label, formatter = self._slider_meta[key]
        slider.set(value)
        label.configure(text=formatter(float(value)))

    def _show_page(self, name):
        page = self._pages.get(name)
        if page:
            page.lift()
        for page_name, button in self._nav_buttons.items():
            selected = page_name == name
            button.configure(
                fg_color=C_RED if selected else "transparent",
                hover_color=C_RED_HOVER if selected else C_SURFACE_ALT,
                text_color="white" if selected else C_MUTED,
            )

    def _apply_config(self):
        self.var_color.set(self.cfg.get("use_color", True))
        self.var_template.set(self.cfg.get("use_template", True))
        self.var_enter.set(self.cfg.get("use_enter", True))
        self.var_exit.set(self.cfg.get("exit_after_accept", False))
        self.var_start_minimized.set(self.cfg.get("start_minimized", False))
        self.var_autostart.set(self.cfg.get("add_to_autostart", False))
        self.var_tg.set(self.cfg.get("telegram_enabled", False))
        self.ent_chat.insert(0, self.cfg.get("telegram_chat_id", ""))
        self._set_slider("threshold", self.cfg.get("match_threshold", 0.75))
        self._set_slider("scan", self.cfg.get("safety_scan_sec", 2.0))
        self._set_slider("retry", self.cfg.get("retry_seconds", 4.0))
        self._set_slider("debounce", self.cfg.get("debounce_seconds", 8.0))

    def _collect_config(self):
        data = dict(self.cfg)
        data.update(
            {
                "use_color": self.var_color.get(),
                "use_template": self.var_template.get(),
                "use_center_click": False,
                "use_enter": self.var_enter.get(),
                "switch_focus": True,
                "focus_mode_configured": True,
                "match_threshold": round(self.sld_threshold.get(), 2),
                "safety_scan_sec": round(self.sld_scan.get(), 1),
                "retry_seconds": round(self.sld_retry.get(), 1),
                "debounce_seconds": round(self.sld_debounce.get(), 1),
                "telegram_enabled": self.var_tg.get(),
                "telegram_chat_id": self.ent_chat.get().strip(),
                "exit_after_accept": self.var_exit.get(),
                "start_minimized": self.var_start_minimized.get(),
                "add_to_autostart": self.var_autostart.get(),
            }
        )
        self.lbl_focus_mode.configure(
            text="✓  Перед Enter Dota всегда выводится на передний план"
        )
        return data

    def _log(self, message):
        # Logs are discarded — journal tab removed for simplicity
        pass

    def _on_engine_event(self, event, generation=None):
        def apply_current():
            if generation is None or generation == self._engine_generation:
                self._apply_engine_event(event)

        self.after(0, apply_current)

    def _apply_engine_event(self, event):
        self._last_event = event
        self._engine_active = event.state is not EngineState.STOPPED
        display = display_for(event)
        colors = {
            "neutral": (C_MUTED, C_SURFACE_ALT),
            "success": (C_GREEN, C_GREEN_SOFT),
            "working": (C_WORK, "#3A2B17"),
            "danger": (C_RED, C_RED_SOFT),
        }
        accent, soft = colors[display.tone]
        self.lbl_status.configure(text=display.title)
        self.lbl_detail.configure(
            text=display.detail or "Dota 2 можно держать свёрнутой"
        )
        self.lbl_header_state.configure(text=f"● {display.title}", text_color=accent)
        self.status_orb.configure(fg_color=soft)
        self.btn_toggle.configure(
            text=display.primary_action,
            fg_color=C_RED if self._engine_active else C_GREEN,
            hover_color=C_RED_HOVER if self._engine_active else C_GREEN_HOVER,
        )
        self.lbl_latest.configure(text=display.title)
        self.lbl_latest_detail.configure(text=display.detail)

    def _toggle_engine(self):
        if self._engine_active:
            self._engine_active = False
            if self.engine:
                self.engine.stop()
            self._apply_engine_event(
                EngineEvent(EngineState.STOPPED, "Остановлен", "Мониторинг выключен")
            )
            return

        cfg = self._collect_config()
        if not any(
            cfg.get(key, False)
            for key in ("use_color", "use_template", "use_enter")
        ):
            self._apply_engine_event(
                EngineEvent(
                    EngineState.STOPPED,
                    "Выберите метод принятия",
                    "Включите цвет, шаблон или резервный Enter",
                )
            )
            return

        self._engine_active = True
        self._apply_engine_event(
            EngineEvent(EngineState.WAITING, "Запускаю", "Инициализация мониторинга")
        )
        self._engine_generation += 1
        generation = self._engine_generation
        self.engine = AutoAcceptEngine(
            cfg,
            log_callback=self._log,
            config_callback=self._collect_config,
            status_callback=lambda event, current=generation: self._on_engine_event(
                event, current
            ),
        )
        self.engine_thread = threading.Thread(target=self.engine.run, daemon=True)
        self.engine_thread.start()

    def _save_settings(self):
        self.cfg = self._collect_config()
        config.save(self.cfg)
        if self.engine and self.engine.running:
            self.engine.update_config(self.cfg)
        try:
            autostart.set_enabled(self.cfg["add_to_autostart"])
        except OSError as exc:
            message = f"Настройки сохранены, но автозагрузка не обновлена: {exc}"
            self.lbl_settings_status.configure(text=message, text_color=C_RED)
            self._log(f"[!] {message}")
            return
        self.lbl_settings_status.configure(text="Настройки сохранены", text_color=C_GREEN)
        self._log("[*] Настройки сохранены")

    def _test_telegram(self):
        chat_id = self.ent_chat.get().strip()
        if not chat_id:
            self.lbl_tg.configure(text="Введите Chat ID", text_color=C_RED)
            return
        self.lbl_tg.configure(text="Проверяю...", text_color=C_MUTED)

        def worker():
            ok, message = tg.test_connection(chat_id)
            self.after(
                0,
                lambda: self.lbl_tg.configure(
                    text=message,
                    text_color=C_GREEN if ok else C_RED,
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _link_telegram(self):
        """Open Telegram bot link and wait for /start to auto-bind Chat ID."""
        import webbrowser
        url = f"https://t.me/{BOT_USERNAME}?start=link"
        webbrowser.open(url)
        self.lbl_link_status.configure(
            text="Ожидание... Нажмите Start в Telegram",
            text_color=C_WORK,
        )

    def _on_chat_id(self, chat_id, username):
        def update():
            self.ent_chat.delete(0, "end")
            self.ent_chat.insert(0, chat_id)
            self.var_tg.set(True)
            suffix = f" (@{username})" if username else ""
            self.lbl_tg.configure(
                text=f"Chat ID получен{suffix}",
                text_color=C_GREEN,
            )
            self.lbl_link_status.configure(
                text=f"✓ Telegram привязан! Отправляю подтверждение...",
                text_color=C_GREEN,
            )
            # Auto-save config with telegram enabled
            self.cfg = self._collect_config()
            config.save(self.cfg)

        self.after(0, update)

        # Send a test-connection confirmation message to the bot
        def send_confirmation():
            ok, message = tg.test_connection(chat_id)
            def show_result():
                if ok:
                    self.lbl_link_status.configure(
                        text=f"✓ Telegram привязан! Подтверждение отправлено",
                        text_color=C_GREEN,
                    )
                else:
                    self.lbl_link_status.configure(
                        text=f"✓ Привязан, но подтверждение не отправлено: {message}",
                        text_color=C_WORK,
                    )
            self.after(0, show_result)

        threading.Thread(target=send_confirmation, daemon=True).start()

    def _show_window(self):
        self.deiconify()
        self.lift()

    def _on_close(self):
        if self.tray:
            self.withdraw()
        else:
            self._real_quit()

    def _real_quit(self):
        tg.stop_background_listener()
        if self.engine and self.engine.running:
            self.engine.stop()
        if self.tray:
            self.tray.stop()
        self.cfg = self._collect_config()
        config.save(self.cfg)
        self.destroy()


def main():
    App().mainloop()
