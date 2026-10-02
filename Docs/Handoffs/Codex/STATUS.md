# Последний статус визуальной части Codex

Дата: 2026-10-02. Последняя поставка: **арена и камера 0.4**. Прочитай arena-camera.md и Docs/Art/ARENA_GUIDE.md, затем материалы/LOD 0.3 вместе с общим PROJECT_STATE.md. Общий файл пока отражает предыдущую интеграционную точку; его обновление после приёма принадлежит Opus.

## Проверено в доступной среде

- Базовые Vanguard/Bulwark и восемь FBX-клипов: прежние50 Blender checks и10 checksum сохранены.
- Новые LOD1/2 обоих бойцов: 5658/3300 triangles, одинаковые20 bones, rigid weights, UV и5slots.
- Шесть PBR PNG 2048²: BaseColor/ORM/Normal на каждого робота, реальные внешние файловые ссылки в .blend.
- Blender QA дополнения:84/84, включая actual FBX round trips, joint positions, rigid motion и UV/texture data.
- Три реальных Blender-рендера текстурированных бойцов и LOD comparisons.
- Оригинальная промышленная арена: 4 180 triangles, 8 slots, .blend/static FBX, три реальных Blender-рендера.
- Actual arena FBX round trip, scale/UV/material/portable image checks и 17 camera pose cases: **61/61** — Docs/Art/ARENA_QA_REPORT.json. Sparse ray diagnostics не подтверждают игровую читаемость: частичное перекрытие пика удара защитой игрока остаётся открытым.
- UI source checks17/6/9 и source-only runtime plugin0.2-draft из предыдущей передачи.

## Подготовлено, но Unreal запуск не выполнен

Первичный editor import/sandbox, importer материалов/LOD, отдельный importer статической арены и C++-плагин menu/HUD/camera/impact. UE отсутствует на текущем Mac; прямого доступа к Windows нет. Asset/presentation contracts остаются drafts, Opus их ещё не принял.

## Следующие задачи по роли Codex

1. На Windows проверить базовый импорт, текстуры/LOD и arena import, сантиметры/оси/rig/tangents/materials; исправить реальные ошибки.
2. По принятому контракту pose/action реализовать IK и visual pose blend, не менять MediaPipe protocol.
3. Свести реальные UE материалы/свет арены, проверить gameplay camera/перекрытия и collision, затем короткий пропускаемый выход бойцов.
4. По действительным commands/settings/tracking snapshots реализовать остальные экраны UMG и локальные косметические повреждения.
5. Проверить packaged build, реальную читаемость/доступность, FPS/VRAM и скорректировать бюджеты.

Не придумывать, что уже есть gameplay/MediaPipe loop, принятый contract, подключение Opus, UE screenshots или готовый бой. При продолжении читать этот статус, фактические manifests и последнюю передачу.
