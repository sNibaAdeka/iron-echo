# Передача визуального UI фундамента Opus

Пакет `codex-ui-0.1`, 2026-10-02. Состояние: prepared source, offline checks passed; runtime UMG unverified.

Дополнение 0.2-draft: native menu/HUD подготовлены в IntegrationDraft/IronEchoVisuals. Новая передача и границы проверки — runtime-visuals.md. Ни этот исходный отчёт, ни новая передача не подтверждают запуск UMG в UE.
Автор источников UI: Codex. Принятый контракт Opus отсутствует; версии `iron-echo-ui-* /0.1` — локальные схемы арт-источников, не контракт gameplay.

## Файлы

- `ArtSource/UI/theme.json` — семантические sRGB цвета, размеры, motion tokens, проверяемые пары контраста.
- `ArtSource/UI/ui_text.ru.json` — русские labels и сообщения; импортировать в единую локализацию проекта.
- `ArtSource/UI/Icons/{camera,play,settings,guard,exit,pause,check,warning,back}.svg` — 9 оригинальных векторных иконок с currentColor и title.
- `ArtSource/UI/Mockups/main-menu-{375,768,1024,1440}.svg`, `calibration-1440.svg`, `hud-1440.svg` — двумерные макеты, каждый помечен «не кадр Unreal».
- `ArtSource/UI/layout_manifest.json` — размеры viewport и control rectangles для повторной проверки.
- `ArtSource/UI/contrast_report.json` — вычисленные проверки источников; runtimeVerified=false.
- `Tools/UI/generate_ui_sources.py` — детерминированный генератор иконок и макетов, Python standard library.
- `Tools/UI/verify_ui.py` — контраст, target sizes/spacing/bounds, primary action count, XML и motion ratio.
- `Docs/Art/UI_SPEC.md` — структура UMG, состояния, требования к адаптеру данных, импорт и runtime checklist.

## Воспроизведение из корня пакета

```powershell
py -3 Tools/UI/generate_ui_sources.py
py -3 Tools/UI/verify_ui.py
```

На macOS проверено Python3.14.5. Внешних Python dependencies нет.
Получено: 17/17 цветовых пар, 6/6 контрольных компоновок и 9/9 SVG icons проходят; exit/enter=0.4, reduced motion duration=0.

## Что требуется для импорта

Сначала принять UI data/command adapter Opus и проектную локализацию. Далее Codex импортирует theme в единый UMG ресурс, иконки — проверенным SVG путём либо прозрачными PNG — и собирает общие widgets. Opus связывает игровые снимки/команды. Пакет не меняет `.uproject`, `Config`, Tracking и gameplay.

Согласовать данные: здоровья/выносливости max/current, раунда/авторитетного времени, tracking state, camera availability, calibration steps, settings acknowledgment. UI не вычисляет урон и не заводит второго авторитетного здоровья. Точные имена типов и методов должен дать Opus.

## Ограничения

- `.uasset`/UMG runtime не созданы; макеты не показывают работающий игровой интерфейс.
- JSON schema не импортирована автоматически в Unreal.
- No runtime contract, no camera access and no Windows build verification.
- Offline contrast относится к непрозрачным sRGB токенам. Итоговый текст и фокус проверить в packaged frame.
- 375/768/1024/1440 — проверочные ширины адаптивной компоновки, не обещание мобильного порта.
- Шрифты не поставляются; выбранный project font и кириллицу требуется проверить.
- Нет сторонних изображений, платных ассетов или внешних UI dependencies. Все иконки созданы в этом пакете.

Получатель должен сохранить единственного автора `.uasset` во время импорта. Не импортировать одновременно с редактором/картой другого агента. При ошибке данных сначала корректировать согласованный адаптер, не дублировать боевые значения внутри widgets.
