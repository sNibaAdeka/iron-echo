# Материалы и LOD — графическая поставка 0.3

Это дополнение к исходным моделям и runtime-черновику. Базовые два FBX, восемь клипов, имена костей, joint positions и пять слотов не заменены. Оптимизация и материалы проверены **в Blender 4.5.7 LTS**; Unreal-импорт этого дополнения ещё не запускался.

## Созданные материалы

На робота — три собственные карты 2048×2048:

| Карта | Данные | Настройка Unreal |
|---|---|---|
| BaseColor | Цвет краски/стали, мягкая вариация поверхности, статический износ | sRGB=true, обычная цветная compression |
| ORM | R: AO=1; G: roughness; B: metallic | sRGB=false, Masks |
| Normal | Tangent-space OpenGL +Y, мелкая поверхность | sRGB=false, Normalmap, **Flip Green Channel=true** |

AO намеренно белая: неподвижное затенение соседней рукой в исходной позе не запекается в движущуюся модель. Остальные два канала настоящие запечённые свойства материалов. Сталь имеет metallic около0.93, латунь около0.92; окрашенная панель в основном неметаллическая, небольшой статический износ допускает metallic до0.233. Rubber и Signal получают собственные значения через исходные материальные участки UV.

Шейдер Blender используется для генерации, затем lookdev-сцена заново подключает **внешние PNG**, а не зависит от незаписанного image buffer. Пути в .blend относительные и проверены после нового открытия. Карты не содержат чужих изображений. Это статическая поверхность; карта износа не является реакцией на игровые попадания.

Unreal master использует три texture samples и сохраняет пять material slots. Параметр WearAmount допускает глобальное косметическое изменение материала; локальных следов удара пока нет. Значение приходит от согласованной команды gameplay, не считается из отдельного визуального здоровья. Эмиссия Signal управляется material instance, остальные слоты не светятся.

## Облегчённые модели

| Уровень | Треугольников на робота | Относительно LOD0 | Применение после проверки камеры |
|---|---:|---:|---|
| LOD0 | 9432 | 100% | Ближний бой, портрет и выход |
| LOD1 | 5658 | 60% | Средняя дистанция |
| LOD2 | 3300 | 35% | Дальний план |

Коллапс применяется к копии исходной геометрии. UV, материальные участки, жёсткие vertex weights и rest skeleton сохраняются; нормали пересчитываются для уменьшенной сетки. Две модели используют те же 20 костей. Сокеты и игровые контактные радиусы здесь не меняются.

Симметрическая **выборочная** оценка расстояния между поверхностями дала примерно2 мм для LOD1 и4.3 мм для LOD2. Это не точная Hausdorff-граница и не доказательство отсутствия заметного перехода в любом ракурсе. Точные значения и число точек — LOD_BUILD_REPORT.json. В близком сравнении более грубые фаски допустимо заметны, поэтому LOD2 не предназначен для постоянного ближнего боя.

Пять material sections остаются пятью на каждом уровне. LOD снижает геометрию, но не обещает уменьшение draw calls, стоимости MediaPipe или времени CPU. Размеры переключения нужно подобрать на реальной камере и RTX3050 после импорта, не по одному Blender-рендеру.

## Проверка и изображения

SURFACE_LOD_QA_REPORT.json содержит реальные Blender-проверки: checksum базовых/новых FBX и текстур; обратный импорт четырёх LOD; кости/joint positions/weights/UV/materials; сохранение длины панелей при изменении позы; размеры, colorspace и portable references текстур после открытия; выборочное покрытие UV и tangent normals. Проверки не сертифицируют Unreal tangents, automatic LOD или производительность.

- Previews/robots-textured-studio.png — два робота с запечёнными картами.
- Previews/vanguard-lod-comparison.png и bulwark-lod-comparison.png — одинаковая Guard pose на LOD0/1/2.
- SURFACE_RENDER_REPORT.json — версия Blender и измеренные границы моделей в кадре studio-рендера.

Изображения являются настоящими offline Blender renders. Скриншотов игры на этом этапе нет.

## Воспроизведение

Из корня репозитория:

```text
blender --background --factory-startup --python Tools/Blender/build_lods.py -- --package .
blender --background --factory-startup --python Tools/Blender/build_surface_atlases.py -- --package . --resolution 2048
blender --background --factory-startup --python Tools/Blender/verify_surface_lods.py -- --package .
blender --background --factory-startup --python Tools/Blender/render_surface_review.py -- --package .
```

Первый генератор build_robots.py создаёт базовые модели/клипы. Если базовые FBX пересозданы, их digest изменится: дополнения нужно тоже пересобрать и проверить. LOD и texture manifests содержат snapshot исходных FBX; importer откажется смешивать разные ревизии.

## Импорт дополнения в Unreal — шаг владельца Art

Сначала подтвердить базовый import/validate и остановить PIE, сохранить изменения, получить исключительную запись Art. Tools/Unreal/Art/import_surface_lods.py не запускается автоматически вместе с первым sandbox: по умолчанию это preflight.

В Python console редактора, подставив настоящий путь на Windows:

```python
import sys
sys.path.insert(0, r"D:\путь\iron-echo\Tools\Unreal\Art")
import import_surface_lods
import_surface_lods.main([])          # preflight, без изменения ассетов
import_surface_lods.main(['--apply']) # первый согласованный импорт Art
```

Создаются новые Texture2D и M/MI в /Game/Art/IronEcho. Через SkeletalMeshEditorSubsystem.import_lod добавляются уровни1/2 в существующий робот; ссылки на Skeleton и имена слотов проверяются. На mesh назначаются atlas material instances. Старые упрощённые материалы сохраняются. .uproject, Config, gameplay и карты не редактируются.

Если LOD уже существуют, повторная запись требует явно переданного текущему автору права и `--replace`; чужие ручные MI/master-изменения не заменяются автоматически. Импорт может частично создать ассеты до ошибки; это не транзакция с rollback. При сбое сохранить traceback и не пересоздавать/удалять всё для обхода диагностики. Отчёт успешного/preflight запуска — Saved/IronEchoArtReports/import_surface_lods.json.

Проверить оба робота с forced LOD0/1/2, оси/сантиметры, joint positions, силуэт, tangents/normal green, seams, эмиссию и все clips. Настроить screen sizes на реальной камере. Затем проверить shader compilation, texture compression/mips/streaming и packaged build. Пока эти пункты **UNVERIFIED**.

## Бюджет памяти

Если шесть карт закодированы в формате8 бит/тексель, их размер с полной цепочкой mip levels примерно32 MiB. Для несжатого RGBA8 та же оценка128 MiB. Это расчёт формата, а не замер текущего Unreal cook; фактические pixel formats, VRAM и выигрыш нужно измерить на Windows.

## Источники API

[Blender bake](https://docs.blender.org/api/4.5/bpy.ops.object.html), [Unreal SkeletalMeshEditorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SkeletalMeshEditorSubsystem?application_version=5.6), [Texture2D](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/Texture2D?application_version=5.6). Классический UE5.6 editor API — подготовленная основа, не подтверждённая версия целевой машины.
