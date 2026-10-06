Latest decision: restored the UI from before the long design-polish prompt, including its muted red accent. Prior polish and subsequent blue experiment are rolled back. Backup of the polished blue version: frontend/.recordings/before-rollback-20261006-231032.zip. Backend and run reducer unchanged.

Latest accent update: user requested muted blue again. Shared accent/primary/hover tokens and favicon now use blue in both themes; neutral charcoal backgrounds and squircle geometry remain unchanged. This supersedes warm-red references below.


## UI polish ? 2026-10-06

The latest pass preserves the layout, charcoal palette, warm red accent and native `corner-shape: squircle`. Shared CSS now extends squircle geometry to form controls and action buttons. Sidebar selection is quieter; headings, labels, tabs and spacing are more restrained. Decorative form numbering, redundant separators, fake avatar and marketing empty-state copy were removed. Workflow labels distinguish not started, waiting, active, completed and failed using existing run state; no reducer/API/business-logic changes. Research emphasizes source counts and excerpts. Examples use functional titles and recordings refreshed from the same components. The existing costs dialog, duration, themes, editing/copy/download and navigation remain intact. Generation still awaits API integration.

Visual review: desktop compose, mobile results, completed draft, expanded research, light costs dialog; native superellipse confirmed in browser. Added a regression check for a failed Writing stage with completed earlier stages, waiting Review and no copy action. Existing responsive and video tests retained.

# Передача работы — AI SDR

Актуальный выбор акцента (2026-10-06, после синего варианта): приглушённый красный в обеих темах, включая подвижную плашку расходов и favicon. Нейтральные тёмные поверхности сохранены. Убран верхний блок Personal workspace / Local project: сервис предназначен для подготовки писем, сущности проектов нет. Старые описания синего/зелёного ниже — история, а не текущее решение.

Последняя визуальная правка 2026-10-06: акценты обеих тем заменены на приглушённые синие (включая favicon, кнопки, навигацию, focus и статусы), тёмные поверхности остались нейтральными. У `.cost-period-thumb` убрана граница; внешняя рамка переключателя сохранена. Обе темы и геометрия рамок просмотрены в браузере, сборка и форматирование проходят. Vite после восстановления локального сервера работает в сессии 93480; перед повторным запуском проверять HTTP/порт через netstat (Get-NetTCPConnection в текущем окружении недоступен).

Уточнение 2026-10-06: тёмные фон/панели/поля возвращены к нейтральным серым; зелёные акценты кнопок сохранены. Рядом с заголовком результата отображается durationSeconds шрифтом 14 px (неизвестное значение — прочерк). В Run costs добавлен переключатель 30 days / 24 hours / This run с подвижной суперэллиптической плашкой, поддержкой drag и клавиатуры. По умолчанию This run; история периодов пока не подключена, текущий запуск не выдаётся за историю. Периоды означают последние 24 часа/30 дней, не календарные сутки. Последняя Vite-сессия: 53345. Видеопримеры перезаписываются с нейтральным фоном и явно иллюстративным временем 12.4 s.

Обновлено 2026-10-05. Следующие решения приоритетнее прежней идеи основного деморежима.

## Запрос пользователя и сделанное

Пользователь готовит проект для фриланс-портфолио и хочет полноценное рабочее приложение с одним режимом. В React основной Compose теперь начинается с пустого брифа. Генерация явно отключена до API; платные вызовы в этой итерации не выполнялись. Python-агенты и Streamlit не изменены.

- Отдельная страница `/#examples`: два встроенных WebM-ролика с постерами, автозапуском без звука, повтором, паузой и текстовым описанием. Учитываются видимость, скрытая вкладка и prefers-reduced-motion. Ролики записаны из общих компонентов на вымышленных данных Northstar; это явно обозначено. Их нужно заменить реальными записями после API.
- Run costs больше не прокручивает главную страницу: это центрированный native dialog с blur и отдельным внешним крестиком. Escape и возврат фокуса проверяются Playwright. Пока нет реальных метрик — прочерки, не фиктивные суммы или нули.
- Блок от Run status до Review required before sending объединён в одну поверхность. Суперэллиптические углы у результата, диалога, кнопок навигации; fallback на border-radius. Светлая/тёмная/системная темы сохранены.
- `src/run.ts` содержит прототип контракта событий и reducer. `RunPanel` показывает действия, частичное письмо, источники, стратегию, ошибку; завершённое письмо можно редактировать, копировать и скачивать. Реальный transport/SSE ещё отсутствует. Таймеры и фикстуры вынесены в `tools/`, не в production bundle.
- Прежний sample playback и восстановление старых sample-черновиков из localStorage удалены из основного продукта. Настоящая история и сохранение — после API.
- Допуск, покупка доступа и три настоящие пробы пока НЕ реализованы. Требования и предварительная политика описаны в `frontend/INTEGRATION.md`, этапы 4/6 ROADMAP обновлены. Счётчик должен приходить с сервера; не делать фиктивные три попытки на клиенте.

## Браузер и запуск

Пользователь работает в расширении Codex для VS Code. Установлен Playwright MCP:

```text
codex mcp add playwright -- cmd /c npx -y @playwright/mcp@latest --browser msedge --isolated --headless
```

Работа браузера реально проверена: переходы, скриншоты, темы и инструменты страницы доступны. `cua` ранее возвращал пустые списки — теперь использовать Playwright, не повторять установку. Профиль Edge изолированный.

Vite слушает http://127.0.0.1:5173. Последний запущенный агентом процесс: сессия 43914. Перед любым запуском проверить доступность/порт, не создавать дубликат. Команды: `cd frontend`, `npm.cmd ci` при необходимости, `npm.cmd run dev`. Есть VS Code task `Frontend: start preview`.

Реальные агенты пока запускаются отдельно через `.venv\Scripts\python.exe -m streamlit run app.py`; это делает платные запросы. API-ключи есть в корневом `.env`, их не читать в вывод и не копировать во frontend.

## Проверки

- TypeScript + production build проходят; typecheck включает src, tools и e2e.
- 12 Vitest тестов: пустой рабочий экран, расходы/неизвестные значения, редактирование/копирование, обработка событий, темы.
- 6 Playwright проверок повторно прошли после финального монтажа видео: 1440/1024/390/360 px, геометрия окна/крестика/blur, Escape и возврат фокуса, сохранение брифа при смене страницы, autoplay/pause, reduced motion и отсутствие белых кадров в начале обоих роликов. Финальные build, format:check и git diff --check также прошли.
- Скриншоты реального браузера просматриваются; видео дополнительно проверять по кадрам: обычный тест currentTime не выявляет пустой старт записи.
- `npm.cmd run record:examples` записывает ролики на локальном Vite, `tools/trim-recording.mjs` убирает белый старт браузера через анализ кадров и bundled FFmpeg. Microsoft Edge и FFmpeg Playwright нужны локально. Файлы примеров в public, временные записи/test-results/.playwright-mcp игнорируются Git.

## Дальше

Визуальные уточнения — в этом же чате, Astra medium (high при смене структуры). После принятия интерфейса — новый чат A для этапов 2–3, Astra high: ошибки графа, действительный API usage, тарифы, настройка моделей, источники и промпты. Не считать текущий frontend подключённым сервисом.

Основные проблемы Python из предыдущего аудита: исследование одним запросом с потерей URL; стратегия без предложения продавца; риск ложного успеха после лимита правок/ошибки JSON; нет надёжного учёта токенов/расходов. Не менять модели лишь ради новизны: сравнить текущую модель с доступными Luna/Sol после проверки актуального API-каталога. Настройки Astra независимы от моделей приложения.

GitHub ранее проверен: `trigonosaurus-rgb/ai-sdr-langgraph`, пользователь разрешил дальнейшее использование. Изменения локальные, без коммита и push. MIT допускает коммерческий hosted-сервис с соблюдением лицензий; открытый репозиторий не означает бесплатные вычисления на аккаунте владельца.

Детальный план — ROADMAP.md; описание фронтенда и команд — frontend/README.md.
