# Передача Opus — визуальный runtime 0.2-draft

Дата: 2026-10-02. Автор записи: Codex. Статус: **исходники подготовлены; UE build/runtime/packaged verification не выполнены**. UE отсутствует на текущем Mac, Windows недоступен в этой сессии.

## Файлы и владение

- `IntegrationDraft/IronEchoVisuals/IronEchoVisuals.uplugin` — disabled-by-default runtime descriptor.
- `IntegrationDraft/IronEchoVisuals/Source/IronEchoVisuals` — Build.cs, module, четыре публичных класса представления, типы адаптера и тема.
- `Tools/UI/generate_runtime_theme.py` — генерирует IETheme.h из общей семантической UI-темы.
- `Tools/Unreal/Art/prepare_vfx_material.py` — editor-подготовка opaque/unlit spark material, отдельный art lock и отчёт.
- `IntegrationDraft/IronEchoVisuals/README.md` — порядок установки, связывания и реальных проверок.

Codex владеет этими исходниками. Opus принимает контракт и переносит согласованный плагин в Game/Plugins, меняет свой .uproject/модуль интеграции и запускает сборки. Сейчас не изменены Game/Config, Tracking и игровые правила. Бинарных .uasset у этого этапа нет.

## Контракт для согласования

Asset contract остаётся `IE-VIS-DRAFT-0.1`. Presentation adapter — `IE-PRESENT-DRAFT-0.1`, ещё не принят. Полные объявления — IEVisualTypes.h. Их задача только отображать авторитетные данные и сообщать пользовательские команды; отдельного протокола MediaPipe или вычисления здоровья нет.

Opus должен сопоставить: UI action ↔ существующая команда; HUD snapshot ↔ авторитетное состояние боя; Tracking presentation ↔ существующая оценка качества; ConfirmedImpact ↔ авторитетное событие контакта с уникальным ID. Подписки и отписки находятся в его адаптере. Конкретные пути gameplay классов и принятая частота событий ещё неизвестны; они не выдуманы в визуальном модуле.

## Импорт и запуск

1. Подтвердить импорт двух роботов существующими Art-скриптами и IE-VIS контракт.
2. Согласовать presentation adapter; скопировать plugin по инструкции README при закрытом UE.
3. Выполнить полную UHT/C++ сборку Development Editor Win64. Исправить реальные ошибки API, сохранив логи.
4. Создать widgets/camera/impact actor в sandbox через адаптер; подготовить spark material отдельным editor-скриптом.
5. Подключить реальные команды/данные Opus, затем проверить PIE и packaged Development.

## Подготовленные ограничения

Меню имеет только четыре действия; калибровка, настройки, пауза и результаты требуют следующей реализации по фактическому контракту. HUD скрыт до валидного снимка и сам не считает ресурсы. Камера требует проверки pivot и Camera collision. VFX — bounded ISM pool, а не финальный Niagara эффект; duplicate history ограничена 512 ID, долговременную сетевую повторную доставку разрешает gameplay adapter. Звука, Sequencer-выхода, IK solver, локальных повреждений и LOD в этом этапе нет.

## Проверки

В среде подготовки прошли: синтаксис 13 Python-файлов, 10 FBX checksum, 17 UI contrast pairs, 6 SVG layouts, 9 SVG icons, совпадение generated theme с JSON, descriptor/module files, локальные include references и порядок generated header в 12 C++ source/header files. Отчёт — Docs/Art/RUNTIME_PREPARATION_REPORT.json. C++ компиляция, UHT, видимое UMG-поведение, actual DPI/focus/screen reader, shader cook, камеры/VFX и FPS/VRAM остаются **UNVERIFIED**. При передаче не считать таблицу требований уже пройденной QA.
