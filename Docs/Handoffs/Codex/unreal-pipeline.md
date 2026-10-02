# Передача редакторской автоматизации Opus

Статус: исходники подготовлены и синтаксически проверены; Unreal execution не проверен.

Файлы: `Tools/Unreal/Art/art_common.py`, `import_art.py`, `validate_import.py`, `build_arena.py`, `run_art_setup.py`.

Вход: `ArtSource/exports/art_manifest.json`, два skeletal FBX и восемь отдельных animation FBX. Корень выходного контента ограничен `/Game/Art/IronEcho`. Скрипты не меняют `.uproject`, Config, gameplay и правила урона.

В движке включить Python Editor Script Plugin и Editor Scripting Utilities, сохранить текущие изменения и остановить PIE. На первый запуск выполнить `run_art_setup.py` через File → Execute Python Script. Отчёты появляются в `Saved/IronEchoArtReports`.

Классический FBX API ориентирован на документацию Unreal 5.6. Версию установленного Windows-движка нужно подтвердить. Если importer или свойство недоступны, сохранить traceback и адаптировать конкретное место; автоматическое переключение на Interchange не реализовано.

Сокеты Fist_L/R на hand_l/r имеют предварительные нулевые offsets. При отсутствии Python setter создать их в Skeleton Editor. Отсутствие сокета остаётся неподтверждённым пунктом и не мешает preview арены; gameplay-приёмка требует подтверждения положения и привязки.

Проверить два робота в Skeletal Mesh Editor, высоту примерно 214.85 см, +X forward, левую/правую руки, пять материалов, общий Skeleton и восемь клипов. Материальные оттенки берутся из manifest. Unreal PBR упрощён относительно Blender noise; WearAmount пока действует на всю поверхность.

Арена — sandbox: primitive-модели, свет и три фиксированные камеры. Нет runtime камеры, кинематографического Sequencer, gameplay collision, VFX попаданий или управления MediaPipe. Это последующие интеграционные работы по принятому контракту.

Нужны от Opus: версия Unreal, лог первого запуска, отчёты import_art/validate_import/build_arena и принятие либо правки IE-VIS-DRAFT-0.1. После этого Codex исправляет графическую часть на основе фактического импорта.
