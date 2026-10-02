# Передача Opus — материалы и LOD 0.3

Задача: IE-ART-SURFACE-LODS. Дата: 2026-10-02. Визуальный asset contract: **IE-VIS-DRAFT-0.1, ещё не принят**. Presentation adapter не меняется. Исходные joint positions, кости, слоты и тайминги клипов сохранены. .uproject/Config/gameplay/Tracking не изменены.

Воспроизводимый Git snapshot: tag `codex-art-v0.3`. Это отметка подготовленных Art sources и Blender QA, не релиз игры.

## Файлы

- ArtSource/Textures/robots: шесть 2048² PNG, texture_manifest.json с source snapshot/checksums.
- ArtSource/exports/lods: четыре skeletal FBX, lod_manifest.json.
- ArtSource/Blender/LODs и Lookdev: реальные .blend для LOD и запечённых материалов.
- Tools/Blender/build_lods.py, build_surface_atlases.py, verify_surface_lods.py, render_surface_review.py.
- Tools/Unreal/Art/import_surface_lods.py — подготовленный preflight/apply importer.
- Docs/Art/SURFACE_LOD_GUIDE.md, LOD_BUILD_REPORT.json, TEXTURE_BUILD_REPORT.json, SURFACE_LOD_QA_REPORT.json, SURFACE_RENDER_REPORT.json.
- Previews/robots-textured-studio.png и два lod-comparison.png — настоящие Blender-рендеры.
- build_robots.py: ограничен сбор основного checksum manifest базовыми10 FBX, чтобы будущая генерация не захватывала чужой LOD manifest.

## Реальные проверки

Blender4.5.7: 84/84 проверок новых ассетов, включая обратный импорт LOD, неизменность исходных10 FBX, skeleton joint positions, rigid motion и portable external textures. LOD на обоих роботах: 9432/5658/3300 triangles. Рендеры осмотрены, кадр studio не обрезает моделей. Более грубая геометрия LOD2 требует выбора подходящей дальности в реальной камере; close-range качество ей не приписывается.

## Интеграция

После базового импорта и согласования Art записи выполнить importer preflight, затем --apply по инструкции SURFACE_LOD_GUIDE.md. Он добавляет LOD1/2 существующим роботам и назначает отдельные atlas materials. OpenGL normal maps: Unreal Flip Green Channel=true. ORM AO намеренно1, roughness/metallic реально запечены. Отчёт успешного запуска сохранить из Saved/IronEchoArtReports.

## Не проверено

UE import/tangents/normal convention в отображении, LOD screen sizes и transitions, shader cook, mips/streaming, реальные draw calls, VRAM/FPS и packaged Windows. Runtime IK, gameplay adapters, калибровка/настройки, выход бойцов и локальные повреждения всё ещё требуют следующих этапов. Статический износ не следует считать реализованной реакцией на удар.

## Владение и следующий шаг

Codex остаётся владельцем новых Art sources и подготовки импорта. .uasset при импорте пишутся одним Art автором. PROJECT_STATE.md по team plan ведёт Opus: после приёма этой передачи обновить общий статус реальными результатами, не заявлять UE PASS по Blender QA. Пока интегратор недоступен, актуальное продолжение визуальной части находится в Docs/Handoffs/Codex/STATUS.md.
