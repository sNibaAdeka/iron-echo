# 005 Codex → интегратор: подтверждённый контакт и время реакции

Дата: 2026-10-03. IronEchoVisuals **0.3-draft**, presentation adapter proposal **IE-PRESENT-DRAFT-0.2**. Исходники, без проверки в Unreal. Новые модели/ринг Claude не получены и не менялись; старые assets сохранены без запуска генераторов.

## Поведение и файлы

UIEContactFeedbackComponent принимает подтверждённое gameplay событие после BeginPlay на game thread, проверяет активацию, EventId и конечные position/normal/intensity, ограничивает intensity до 0..1. Повтор последних 512 ID возвращает false до camera/VFX/delegate. Отсутствие spark material не мешает другим потребителям. true подтверждает приём данных, а не рендер. Нулевая интенсивность принимается без sparks/kick/hold.

GetReactionPlayRate возвращает 0 на 40–65 мс и 1 после deadline, по FPlatformTime. Контакты не продлевают активное окно; следующие 100 мс — gap без нового hold. Reduced motion отменяет hold сразу. Компонент без Tick, с weak targets, не меняет позу/physics/ресурсы/время игры. OnImpactAccepted предназначен для косметического reaction adapter.

AIEVisualCameraRig получает ApplyConfirmedImpact(Event) с отдельной bounded history. Pulse затухает за 160 мс реального времени, ограничен 1.5 см при ShakeScale=1, очищается при потере target/reduced motion. Камерный Tick разрешён при паузе для сброса истёкшего offset. Старый float kick deprecated, не имеет dedup. Follow/SpringArm требуют проверки новой геометрии.

Файлы Codex:

- IntegrationDraft/IronEchoVisuals/Source/IronEchoVisuals/Public/IEContactPolicy.h — engine-independent runtime policy.
- Public/IEContactFeedbackComponent.h, Private/IEContactFeedbackComponent.cpp и Private/IEImpactValidation.h внутри того же модуля — компонент, валидация и delegate.
- Public/IEVisualCameraRig.h и Private/IEVisualCameraRig.cpp — обновлённая camera.
- IntegrationDraft/IronEchoVisuals/IronEchoVisuals.uplugin и README.md — версия и точное подключение.
- Tools/QA/contact_policy_tests.cpp, run_contact_policy_tests.py и Docs/Art/CONTACT_POLICY_QA_REPORT.json — фактический portable check.

Game/.uproject, Config, gameplay, Tracking, Realistic/** и PROJECT_STATE не менялись. Бинарных UE assets на этом этапе нет.

## Подключение — Opus на Windows

1. Принять IE-PRESENT-DRAFT-0.2, подтвердить UE version/GameCameraClass и маршрут контактов. При закрытом UE перенести plugin одним автором в Game/Plugins, включить в .uproject и выполнить полную UHT/C++ Development Editor Win64 сборку.
2. Создать активный компонент на локальном presentation actor. ConfigureTargets получает настоящие camera/spark actors, возможно nullptr. Подключить только ApplyConfirmedImpact из одного авторитетного потока. Не отправлять одновременно тот же контакт напрямую старым методам.
3. EventId уникален между матчами. В Event пока нет fighter ID: recipient/defender определяет адаптер. Если компонентов несколько, только один владеет общей camera/sparks, а каждый reaction recipient получает только свои контакты.
4. OnImpactAccepted запускает положительный косметический reaction clip. Не сбрасывать его время на каждом burst event: hold policy не исправляет независимые перезапуски в адаптере.
5. На game thread в обновлении AnimInstance копировать GetReactionPlayRate в scalar для AnimGraph. Умножить скорость отдельного reaction Sequence Player. Без root motion, gameplay notifies и общей sync group с gameplay. Getter не thread-safe; worker graph получает скопированное значение. Не применять rate к tracking/base pose, attack, locomotion, knockdown/getup или таймеру.
6. SetReducedMotion передаёт режим обоим target. ResetPresentationSession очищает только свой hold/history, сохраняет preference; вызывать после прекращения старой подписки. У camera/sparks независимые истории — старые ID не переиспользовать. EndPlay очищает ссылки и delegate.
7. Проверить PIE, затем packaged Development Win64, записать реальные логи/видео. Подробные методы и ограничения — README плагина.

## Фактические проверки

`python3 Tools/QA/run_contact_policy_tests.py --report Docs/Art/CONTACT_POLICY_QA_REPORT.json` компилирует **тот же IEContactPolicy.h, который включён в runtime**, clang++ C++17, -Wall -Wextra -Werror -pedantic. Пройдены 10 сценариев: invalid ID/NaN/Inf/time, duplicate, 10 000 rapid events без продления hold, duration/intensity, reduced motion/reset, FIFO eviction и bounded 100 000-event history, clock failure/rewind/длинная пауза, release на 15/30/60/144 FPS, pulse bounds и неверный input. Report содержит SHA256 проверенных исходников.

Это компиляция portable policy, **не Unreal module/UHT/AnimGraph**. Package integrity отдельно проверяет checksum старых assets без пересоздания.

## Проверки в Unreal — пока все UNVERIFIED

| Случай | Ожидаемое поведение |
|---|---|
| Duplicate | Второй приём=false; нет второго delegate/kick/sparks |
| Missing spark material/target | Остальные потребители работают; event=true |
| Intensity=0 | Нет sparks/kick/hold; adapter не запускает clip |
| Burst | Hold не продлевается, adapter не перезапускает clip бесконечно |
| Reduced motion во время hold | Rate=1, offset=0, текущие искры очищаются |
| Pause/hitch/deactivate/EndPlay | Нет застрявшего playback или подписок |
| Получатель | Правильный робот; один владелец общей camera/VFX |
| Gameplay isolation | Tracking, damage, collision, physics, timer продолжаются |
| IE-1 camera | Проверить pivot, канаты/столбы, близкую дистанцию и читаемость атак |

## Ограничения

Это hold времени **reaction clip**, а не полного procedural pose. Он станет видимым после подключения player в принятом AnimBP. Готового AnimBP, IE-1 knockdown/getup, выхода бойцов и звука пока нет. Старый KO не выдаётся за knockdown. UE на этом Mac отсутствует, Windows не подключён, FPS/VRAM не измерены. Следующий шаг требует UE project + skeleton/socket contract и phase interfaces от Claude.

Публичные сигнатуры сверены по официальным [UActorComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/Components/UActorComponent?application_version=5.5), [FTickFunction](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/Engine/FTickFunction?application_version=5.5), [Sequence Player](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/Animation/FAnimNode_SequencePlayer?application_version=5.5) и [Core clock](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Core/GStartTime?application_version=5.5). Это не заменяет build под установленную версию.
