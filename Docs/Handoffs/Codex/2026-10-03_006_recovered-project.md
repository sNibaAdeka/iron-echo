# Восстановление исходников Claude и camera adapter

Обновлено 2026-10-03. Найдено и скачано вложение `iron-echo-claude-wizardly-pascal.bundle`
из более раннего сообщения облачной сессии Claude. Bundle проверен; девять исходных коммитов
восстановлены с сохранением истории, tip `2b3773eb2a4f042ec1bf9c7b242b39af958fbfc7`.
SHA256: `4f6ae5a42d2542e3c701291b8fdef23b55c6c5d5232e66e123194bf8f3363613`.

В `sNibaAdeka/iron-echo` теперь доступны:

- [Исходная работа Claude](https://github.com/sNibaAdeka/iron-echo/tree/claude/recovered-wizardly-pascal/IronEcho).
- [Кандидат интеграции](https://github.com/sNibaAdeka/iron-echo/tree/codex/contract-1.1-integration/IronEcho),
  коммит Codex `2005a0f`: plugin source + game-module adapter + registration patch.
- [Инструкция Windows](https://github.com/sNibaAdeka/iron-echo/blob/codex/contract-1.1-integration/IronEcho/Docs/Art/CONTRACT_CAMERA_INTEGRATION.md).
- [QA](https://github.com/sNibaAdeka/iron-echo/blob/codex/contract-1.1-integration/IronEcho/Docs/Art/RECOVERY_AND_INTEGRATION_QA.json).

Реальный контракт Claude — ROBOT_VISUAL_CONTRACT **1.1**, Manny-like 21 обязательная кость и lower-case
fist_l/fist_r/hit_head/hit_body. Старый skeleton Codex несовместим; его автоимпорт не запускать.
Не исправлять контракт Claude через draft skeleton. Realistic модели/ринг остаются за Claude.

Адаптер камеры читает GameState, следует игроку, выбирает соперника/грушу и маршрутизирует
HitConfirmed/Blocked защитнику. В CombatSim GuardBroken сопровождается HitConfirmed; рисуется один
confirmed effect. По груше — без металлических искр. Gameplay/Source/Config Claude сохранены;
точный патч регистрации требует передачи интегратору, он ещё не применён. HUD/menu source перенесены,
но gameplay adapter и AnimBP нокдаун/подъём ещё не готовы.

Проверено здесь: Core 58/58 AppleClang+ASan/UBSan; tracker 36 passed + 1 skipped (нет весов модели);
robot validator unit tests 6/6; portable contact policy 10/10. Ownership, syntax/include/JSON и patch
preflight прошли. Gitleaks восстановленной истории и новых исходников — 0 findings.
Unreal/UHT, реальная камера, Windows package, FPS/VRAM не проверены.

В bundle есть генераторы и рендеры, но нет .blend/.fbx/запечённых игровых текстур/.uasset/.umap/.exe.
Последующая переделка головы/перчаток могла остаться вне коммитов облачного рабочего дерева.
Main этого Art-репозитория сохраняет существующую структуру; новый Unreal-проект доступен именно
в указанных ветках. Это ещё не готовая игра.

Интернет-проверка: [Claude teleport](https://code.claude.com/docs/en/claude-code-on-the-web) требует
уже опубликованной ветки. Восстановление сделано через найденный bundle.
[Epic dependency hierarchy](https://dev.epicgames.com/documentation/en-us/unreal-engine/plugins-in-unreal-engine)
проверена при отделении project adapter от plugin.
[MaterialUsage 5.6](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialUsage?application_version=5.6)
подтвердила правильное имя `MATUSAGE_INSTANCED_STATIC_MESHES`; исправлена опечатка в старом
prepare_vfx_material.py. Исполнение этого Python в Unreal остаётся непроверенным.
