#!/usr/bin/env python3
"""Generate original SVG sources and honest UMG layout mockups, no engine required."""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "ArtSource" / "UI"
THEME = json.loads((UI / "theme.json").read_text(encoding="utf-8"))
C = THEME["colors"]
COPY = json.loads((UI / "ui_text.ru.json").read_text(encoding="utf-8"))
ICONS = {
    "camera": ('Камера', '<rect x="2" y="6" width="20" height="15" rx="2"/><path d="M7 6l2-3h6l2 3"/><circle cx="12" cy="13" r="4"/>'),
    "play": ('Начать', '<path d="M7 3l14 9-14 9z"/>'),
    "settings": ('Настройки', '<path d="M4 3v18M12 3v18M20 3v18"/><path d="M1 7h6M9 16h6M17 10h6"/>'),
    "guard": ('Защитная стойка', '<path d="M12 2l8 4v6c0 5-4 8-8 10-4-2-8-5-8-10V6z"/><path d="M8 12l3 3 5-6"/>'),
    "exit": ('Выход', '<path d="M10 3H3v18h7M9 12h13M17 7l5 5-5 5"/>'),
    "pause": ('Пауза', '<path d="M7 3v18M17 3v18"/>'),
    "check": ('Готово', '<path d="M3 12l6 6L21 5"/>'),
    "warning": ('Предупреждение', '<path d="M12 2L1 21h22zM12 8v6M12 18h.01"/>'),
    "back": ('Назад', '<path d="M21 12H3M10 5l-7 7 7 7"/>')
}


class Svg:
    def __init__(self, width: int, height: int, screen: str):
        self.width, self.height, self.screen = width, height, screen
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">IRON ECHO — {escape(screen)} — макет</title>',
                      '<desc id="desc">Двумерный макет интерфейса. Не скриншот Unreal Engine. Все показанные игровые значения — примеры.</desc>']
        self.controls: list[dict] = []
        self.rect(0, 0, width, height, "background")

    def rect(self, x, y, w, h, fill, stroke=None, radius=0, thickness=1):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{C[fill]}"' +
                          (f' stroke="{C[stroke]}" stroke-width="{thickness}"' if stroke else '') + '/>')

    def text(self, x, y, content, size=18, token="text", weight=400, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" fill="{C[token]}" font-family="{THEME["typography"]["mockupFont"]}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(content)}</text>')

    def line(self, x1, y1, x2, y2, token="outline", thickness=1):
        self.parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{C[token]}" stroke-width="{thickness}"/>')

    def icon(self, name, x, y, size=24, token="text"):
        self.parts.append(f'<g transform="translate({x} {y}) scale({size / 24})" fill="none" stroke="{C[token]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name][1]}</g>')

    def button(self, identity, x, y, w, label, icon=None, primary=False, disabled=False, focused=False):
        h = THEME["metrics"]["buttonHeight"]
        fill = "disabledSurface" if disabled else "primary" if primary else "surface"
        fg = "disabledText" if disabled else "onPrimary" if primary else "text"
        self.rect(x, y, w, h, fill, None if primary else "outline", THEME["metrics"]["radius"])
        if focused:
            self.rect(x - 5, y - 5, w + 10, h + 10, "background", "focus", 6, 3)
            self.rect(x, y, w, h, fill, None if primary else "outline", 4)
        if icon:
            self.icon(icon, x + 18, y + 16, 24, fg)
        self.text(x + (56 if icon else 20), y + 35, label, 18, fg, 600)
        self.controls.append({"id": identity, "x": x, "y": y, "width": w, "height": h,
                              "primary": primary, "disabled": disabled, "focused": focused})

    def save(self, name):
        target = UI / "Mockups" / name
        target.write_text('\n'.join(self.parts + ['</svg>']) + '\n', encoding="utf-8")
        return {"file": str(target.relative_to(ROOT)), "screen": self.screen,
                "width": self.width, "height": self.height, "controls": self.controls,
                "artifactType": "SVG layout mockup; not an Unreal screenshot"}


def menu(width: int, height: int):
    s = Svg(width, height, "Главное меню")
    p = 16 if width < 768 else 48 if width < 1440 else 64
    panel = min(width - p * 2, 440)
    s.text(p, 32, "МАКЕТ • НЕ КАДР UNREAL", 16, "textMuted")
    s.text(p, 122, COPY["menu.title"], 44 if width < 768 else 64, weight=700)
    if width < 768:
        s.text(p, 168, "ТВОИ ДВИЖЕНИЯ.", 20, "primary", 600)
        s.text(p, 196, "ЕГО УДАРЫ.", 20, "primary", 600)
    else:
        s.text(p, 170, COPY["menu.subtitle"], 20, "primary", 600)
    s.text(p, 240, "Один ринг. Два робота.", 20)
    s.text(p, 270, "Управляй стойкой, уклонами и ударами.", 16 if width < 768 else 18, "textMuted")
    s.text(p, 316, "Пример: камера ещё не выбрана", 16, "warning")
    s.button("configure_camera", p, 344, panel, COPY["menu.camera"], "camera", primary=True, focused=True)
    s.button("start_match", p, 416, panel, COPY["menu.start"], "play", disabled=True)
    s.button("settings", p, 488, panel, COPY["menu.settings"], "settings")
    s.button("quit", p, 560, panel, COPY["menu.quit"], "exit")
    s.text(p, 656, "Нужна камера и место для движения рук.", 16, "textMuted")
    s.text(p, 685, "Данные камеры обрабатываются локально.", 16, "textMuted")
    if width >= 1024:
        x = p + panel + 60
        w = width - p - x
        s.rect(x, 176, w, height - 276, "surface")
        s.text(x + 24, 210, "ЗОНА ФОНОВОЙ СЦЕНЫ", 16, "textMuted")
        # Quiet graphic suggests the ring; it is not a model or scene proof.
        cy = height * 0.59
        s.line(x + 28, cy + 64, x + w - 28, cy + 64, "primary", 2)
        s.line(x + 28, cy + 28, x + w - 28, cy + 28, "outline", 1)
        for px in [x + 28, x + w - 28]:
            s.line(px, cy - 44, px, cy + 122, "outline", 4)
        s.text(x + w / 2, cy - 32, "Графика из Unreal", 22, "text", 600, "middle")
        s.text(x + w / 2, cy, "подключается после импорта", 16, "textMuted", anchor="middle")
    return s.save(f"main-menu-{width}.svg")


def calibration():
    s = Svg(1440, 900, "Калибровка — шаг выбора камеры")
    s.text(64, 34, "МАКЕТ • НЕ КАДР UNREAL", 16, "textMuted")
    s.text(64, 116, COPY["calibration.title"], 42, weight=700)
    s.text(64, 162, "ШАГ 1 / 3  •  ВЫБОР КАМЕРЫ", 18, "primary", 600)
    s.rect(64, 206, 820, 462, "surface", "outline", 4)
    s.icon("camera", 440, 300, 64, "textMuted")
    s.text(474, 402, "Здесь будет локальный предпросмотр", 22, "text", 600, "middle")
    s.text(474, 437, "Макет не открывает камеру", 18, "textMuted", anchor="middle")
    s.text(920, 236, "Перед началом", 24, weight=700)
    lines = ["Встаньте на расстоянии,", "при котором видны голова,", "кисти и таз.", "", "Свет должен падать на вас.", "Освободите место для рук."]
    for n, content in enumerate(lines):
        s.text(920, 284 + n * 29, content, 18, "textMuted")
    s.text(64, 714, "Камера", 18, weight=600)
    s.button("camera_device", 64, 730, 390, COPY["camera.none"], "camera")
    s.button("preview_toggle", 480, 730, 340, COPY["camera.previewHide"])
    s.text(920, 520, "Обработка на этом компьютере.", 18, "success")
    s.text(920, 549, "Запись выключена.", 18, "success")
    s.text(920, 602, "Сначала выберите камеру.", 16, "warning")
    s.button("begin_calibration", 920, 632, 440, COPY["calibration.start"], "guard", primary=True, disabled=True)
    s.button("back", 64, 820, 190, COPY["calibration.back"], "back")
    return s.save("calibration-1440.svg")


def hud():
    s = Svg(1440, 900, "HUD боя")
    s.text(24, 24, "МАКЕТ • ДАННЫЕ ПРИМЕРА • НЕ КАДР UNREAL", 16, "textMuted")
    for x, label, token, health, stamina in [(24, "Игрок", "healthPlayer", 82, 64), (1016, "Противник", "healthOpponent", 76, 58)]:
        s.rect(x, 44, 400, 144, "surface", radius=4)
        s.text(x + 20, 78, label, 22, weight=700)
        s.text(x + 20, 108, f"Целостность  {health} / 100", 16)
        s.rect(x + 20, 120, 360, 14, "surfaceRaised", radius=2)
        s.rect(x + 20, 120, 360 * health / 100, 14, token, radius=2)
        s.text(x + 20, 164, f"Выносливость  {stamina} / 100", 16, "textMuted")
    s.rect(570, 44, 300, 112, "surface", radius=4)
    s.text(720, 79, "РАУНД 1 / 3", 18, "textMuted", 600, "middle")
    s.text(720, 131, "02:14", 40, "text", 700, "middle")
    s.text(720, 438, "ЗОНА БОЯ", 22, "textMuted", 600, "middle")
    s.text(720, 469, "Силуэты и руки противника должны оставаться свободными", 18, "textMuted", anchor="middle")
    s.rect(896, 804, 520, 72, "surface", radius=4)
    s.icon("check", 916, 828, 24, "success")
    s.text(956, 847, COPY["tracking.stable"], 18, "success", 600)
    s.button("pause", 24, 820, 180, COPY["hud.pause"], "pause")
    s.text(226, 854, "Esc", 16, "textMuted")
    return s.save("hud-1440.svg")


def main():
    (UI / "Icons").mkdir(parents=True, exist_ok=True)
    (UI / "Mockups").mkdir(parents=True, exist_ok=True)
    for name, (title, paths) in ICONS.items():
        source = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" role="img" aria-labelledby="title">'
                  f'<title id="title">{escape(title)}</title>{paths}</svg>\n')
        (UI / "Icons" / f"{name}.svg").write_text(source, encoding="utf-8")
    layouts = [menu(375, 812), menu(768, 1024), menu(1024, 768), menu(1440, 900), calibration(), hud()]
    (UI / "layout_manifest.json").write_text(json.dumps({"schema": "iron-echo-ui-layout/0.1", "layouts": layouts}, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
    print(f"Generated {len(ICONS)} SVG icons and {len(layouts)} labeled layout mockups.")


if __name__ == "__main__":
    main()
