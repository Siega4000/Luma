"""
Дизайн-система Luma.

Один источник правды для цвета, типографики, радиусов, отступов
и состояний компонентов. Всё, что рисует интерфейс, берёт значения
отсюда — в коде компонентов не должно быть «сырых» hex-цветов.

Принципы:
  * тёмная тема как основная, глубокий графит вместо чёрного;
  * нейтральная серая шкала и ровно один сдержанный акцент (мята);
  * тонкие границы вместо теней, минимум декора;
  * контраст текста не ниже 4.5:1, видимый фокус на всех элементах;
  * анимации 150-250 мс только там, где они несут смысл.
"""

from __future__ import annotations

# --------------------------------------------------------------- цвет

COLORS = {
    # поверхности
    "bg": "#0C0C0F",            # фон окна — глубокий графит
    "surface": "#121216",       # панели, поля ввода, подложка очереди
    "surface_hover": "#17171C",
    "surface_active": "#1D1D23",
    "overlay": "#141419",       # диалоги, всплывающие меню

    # границы
    "border": "#212128",
    "border_strong": "#2C2C35",
    "divider": "#1A1A20",

    # текст
    "text": "#F5F5F7",          # 17.9:1
    "text_muted": "#9C9CA6",    # 7.2:1
    "text_faint": "#6A6A75",    # только декор и разделители

    # акцент — сдержанный фиолетовый
    "accent": "#7B7BF5",        # текст, иконки, прогресс (5.6:1)
    "accent_fill": "#625FE8",   # заливка кнопки (белый текст 4.9:1)
    "accent_hover": "#6F6CF0",
    "accent_active": "#5752D4",
    "accent_dim": "#1C1B33",    # подложка пилюль и подсветок
    "accent_soft": "#A5A3F7",   # текст на подложке акцента
    "on_accent": "#FFFFFF",

    # статусы
    "success": "#52C77E",
    "success_dim": "#10281A",
    "warning": "#E0B341",
    "warning_dim": "#2A2410",
    "error": "#EF6B6B",
    "error_dim": "#2E1618",
}

# ---------------------------------------------------------- типографика

# Inter — основной; на Windows без Inter подхватится Segoe UI Variable.
FONT_UI = '"Inter", "Segoe UI Variable Text", "Segoe UI", sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", "SF Mono", monospace'

TYPE = {
    "display": 17,   # имя приложения
    "title": 14,     # заголовок карточки
    "body": 13,      # основной текст
    "secondary": 12, # вторичный текст
    "caption": 11,   # метки, мета-данные
}

# ------------------------------------------------------- геометрия

RADIUS = {"sm": 6, "md": 8, "lg": 12, "pill": 999}
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

SIZE = {
    "titlebar": 44,
    "statusbar": 34,
    "input_min": 46,
    "input_max": 118,
    "button": 46,
    "button_sm": 30,
    "cover": 56,
    "icon": 16,
    "row": 76,
}

# Длительности анимаций (мс)
MOTION = {"fast": 120, "base": 180, "slow": 240}


def _qss(check_icon: str = "") -> str:
    c = COLORS
    check_rule = f"image: url({check_icon});" if check_icon else ""
    return f"""
* {{
    font-family: {FONT_UI};
    font-size: {TYPE['body']}px;
    outline: none;
}}

QWidget#Root, QDialog {{
    background-color: {c['bg']};
    color: {c['text']};
}}

/* ---------------- Заголовок окна ---------------- */

QWidget#TitleBar {{
    background-color: {c['bg']};
    border-bottom: 1px solid {c['divider']};
}}

QLabel#Wordmark {{
    color: {c['text']};
    font-size: {TYPE['display']}px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}

QFrame#TitleDivider {{
    background-color: {c['border']};
    border: none;
}}

QPushButton#WindowButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS['sm']}px;
    padding: 0;
}}
QPushButton#WindowButton:hover {{ background-color: {c['surface_hover']}; }}
QPushButton#WindowButton:pressed {{ background-color: {c['surface_active']}; }}
QPushButton#WindowButton:focus {{ border-color: {c['accent']}; }}

QPushButton#CloseButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS['sm']}px;
}}
QPushButton#CloseButton:hover {{ background-color: {c['error']}; }}
QPushButton#CloseButton:pressed {{ background-color: #C64A41; }}
QPushButton#CloseButton:focus {{ border-color: {c['accent']}; }}

/* ---------------- Поле ввода ссылок ---------------- */

QFrame#InputShell {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['lg']}px;
}}
QFrame#InputShell[state="focus"] {{ border-color: {c['accent']}; }}
QFrame#InputShell[state="error"] {{ border-color: {c['error']}; }}

QPlainTextEdit#UrlInput {{
    background: transparent;
    color: {c['text']};
    border: none;
    padding: 0;
    font-size: {TYPE['body']}px;
    selection-background-color: {c['accent']};
    selection-color: {c['on_accent']};
}}


QLabel#InputHint {{
    color: {c['text_muted']};
    font-size: {TYPE['caption']}px;
}}
QLabel#InputError {{
    color: {c['error']};
    font-size: {TYPE['caption']}px;
}}

/* ---------------- Кнопки ---------------- */

QPushButton#Primary {{
    background-color: {c['accent_fill']};
    color: {c['on_accent']};
    border: 2px solid transparent;
    border-radius: {RADIUS['md']}px;
    padding: 0 22px;
    font-size: {TYPE['body']}px;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background-color: {c['accent_hover']}; }}
QPushButton#Primary:pressed {{ background-color: {c['accent_active']}; }}
QPushButton#Primary:disabled {{
    background-color: {c['surface_active']};
    color: {c['text_faint']};
}}
QPushButton#Primary:focus {{ border-color: {c['text']}; }}

QPushButton#IconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS['sm']}px;
    padding: 0;
}}
QPushButton#IconButton:hover {{ background-color: {c['surface_active']}; }}
QPushButton#IconButton:pressed {{ background-color: {c['surface']}; }}
QPushButton#IconButton:focus {{ border-color: {c['accent']}; }}

/* ---------- Метки площадок ---------- */

QFrame#PlatformChip {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['pill']}px;
}}
QFrame#PlatformChip[active="yes"] {{
    background-color: {c['accent_dim']};
    border-color: {c['accent']};
}}
QLabel#ChipText {{
    color: {c['text_muted']};
    font-size: {TYPE['secondary']}px;
    background: transparent;
}}
QFrame#PlatformChip[active="yes"] QLabel#ChipText {{ color: {c['text']}; }}

QPushButton#Secondary {{
    background-color: transparent;
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['md']}px;
    padding: 0 18px;
    font-size: {TYPE['body']}px;
}}
QPushButton#Secondary:hover {{
    background-color: {c['surface_hover']};
    border-color: {c['text_faint']};
}}
QPushButton#Secondary:pressed {{ background-color: {c['surface_active']}; }}
QPushButton#Secondary:disabled {{ color: {c['text_faint']}; border-color: {c['border']}; }}
QPushButton#Secondary:focus {{ border-color: {c['accent']}; }}

QPushButton#Ghost {{
    background: transparent;
    color: {c['text_muted']};
    border: 1px solid transparent;
    border-radius: {RADIUS['sm']}px;
    padding: 4px 10px;
    font-size: {TYPE['secondary']}px;
    text-align: left;
}}
QPushButton#Ghost:hover {{ background-color: {c['surface_hover']}; color: {c['text']}; }}
QPushButton#Ghost:pressed {{ background-color: {c['surface_active']}; }}
QPushButton#Ghost:focus {{ border-color: {c['accent']}; }}

/* ---------------- Очередь ---------------- */

QScrollArea#Queue {{ background: transparent; border: none; }}
QWidget#QueueBody {{ background: transparent; }}

QFrame#QueuePanel {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['lg']}px;
}}

QFrame#TrackRow {{
    background-color: transparent;
    border: none;
    border-bottom: 1px solid {c['divider']};
}}
QFrame#TrackRow:hover {{ background-color: {c['surface_hover']}; }}
QFrame#TrackRow[last="yes"] {{ border-bottom: none; }}
QFrame#TrackRow[active="yes"] {{ background-color: {c['surface_hover']}; }}
QFrame#StatusPillHolder {{ background: transparent; }}

/* ---------- Пилюля статуса ---------- */

QFrame#StatusPill {{
    border-radius: 11px;
}}
QLabel#StatusPillText {{
    font-size: {TYPE['caption']}px;
    font-weight: 500;
    background: transparent;
}}

QLabel#RowSpeed {{
    color: {c['text_muted']};
    font-size: {TYPE['caption']}px;
}}
QLabel#RowSize {{
    color: {c['text_faint']};
    font-size: {TYPE['caption']}px;
}}

QLabel#CardTitle {{
    color: {c['text']};
    font-size: {TYPE['title']}px;
    font-weight: 500;
}}
QLabel#CardMeta {{
    color: {c['text_muted']};
    font-size: {TYPE['secondary']}px;
}}
QLabel#CardStatus {{
    font-size: {TYPE['caption']}px;
    font-weight: 500;
}}
QLabel#Cover {{
    background-color: {c['surface_active']};
    border-radius: {RADIUS['md']}px;
}}

QLabel#SectionLabel {{
    color: {c['text']};
    font-size: {TYPE['title']}px;
    font-weight: 600;
}}

QLabel#EmptyTitle {{
    color: {c['text_muted']};
    font-size: {TYPE['body']}px;
}}
QLabel#EmptyHint {{
    color: {c['text_faint']};
    font-size: {TYPE['secondary']}px;
}}

/* ---------------- Прогресс ---------------- */

QProgressBar {{
    background-color: {c['surface_active']};
    border: none;
    border-radius: 2px;
    height: 3px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 2px;
}}
QProgressBar#RowProgress {{
    background-color: {c['surface_active']};
    height: 4px;
    border-radius: 2px;
}}

/* ---------------- Нижняя панель ---------------- */

QWidget#StatusBar {{
    background-color: {c['bg']};
    border-top: 1px solid {c['divider']};
}}
QLabel#StatusText {{
    color: {c['text_muted']};
    font-size: {TYPE['caption']}px;
}}

/* ---------------- Диалоги и меню ---------------- */

QMenu {{
    background-color: {c['overlay']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['md']}px;
    padding: 5px;
}}
QMenu::item {{
    color: {c['text']};
    padding: 7px 14px;
    border-radius: {RADIUS['sm']}px;
    font-size: {TYPE['secondary']}px;
}}
QMenu::item:selected {{ background-color: {c['surface_active']}; }}
QMenu::item:disabled {{ color: {c['text_faint']}; }}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 5px 8px;
}}

QCheckBox {{
    color: {c['text']};
    font-size: {TYPE['body']}px;
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border_strong']};
    border-radius: 4px;
    background: {c['surface']};
}}
QCheckBox::indicator:hover {{ border-color: {c['text_faint']}; }}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
    {check_rule}
}}
QCheckBox:focus {{ color: {c['accent']}; }}

QLabel#DialogTitle {{
    color: {c['text']};
    font-size: 15px;
    font-weight: 600;
}}
QLabel#FieldLabel {{
    color: {c['text']};
    font-size: {TYPE['body']}px;
}}
QLabel#FieldHint {{
    color: {c['text_muted']};
    font-size: {TYPE['caption']}px;
}}

QTextEdit#LogView {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    padding: 12px;
    font-family: {FONT_MONO};
    font-size: {TYPE['secondary']}px;
    color: {c['text_muted']};
}}

/* ---------------- Прокрутка ---------------- */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_faint']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------------- Всплывающее уведомление ---------------- */

QFrame#Toast {{
    background-color: {c['overlay']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['lg']}px;
}}
QLabel#ToastText {{
    color: {c['text']};
    font-size: {TYPE['secondary']}px;
}}
"""


STYLESHEET = _qss()


def build_stylesheet(check_icon_path: str = "") -> str:
    """QSS с подставленной галочкой чекбокса (путь к PNG в кэше приложения)."""
    return _qss(check_icon_path.replace("\\", "/"))

# Пилюли статусов очереди: статус -> (цвет текста, цвет подложки)
STATUS_PILL = {
    "queued": (COLORS["text_muted"], COLORS["surface_active"]),
    "resolving": (COLORS["text_muted"], COLORS["surface_active"]),
    "downloading": (COLORS["accent_soft"], COLORS["accent_dim"]),
    "converting": (COLORS["accent_soft"], COLORS["accent_dim"]),
    "done": (COLORS["success"], COLORS["success_dim"]),
    "no_cover": (COLORS["warning"], COLORS["warning_dim"]),
    "error": (COLORS["error"], COLORS["error_dim"]),
    "cancelled": (COLORS["text_faint"], COLORS["surface_active"]),
}

LOG_COLORS = {
    "info": COLORS["text_muted"],
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "error": COLORS["error"],
}
