# AquaTwin — питч, демо, деплой и подача заявки

> Всё, что нужно для сцены: текст выступления на английском, сценарий живого демо с запасными планами,
> деплой, ответы на вопросы и чек-лист подачи формы.
>
> Обновлено 11.10.2026 под версию 2 продукта (`AQUATWIN_TZ_V2.md`). Все цифры в тексте взяты из `reports/calibration.json`.

---

## 1. Питч на 3 минуты (EN)

Тайминг рассчитан на ~130 слов в минуту. В скобках — номер слайда.

**[1 · Cover] — 10 s**
> Hi, we're [Name 1] and [Name 2] from Tomorrow School. This is AquaTwin.

**[2 · Problem] — 25 s**
> Farming uses about seventy percent of the world's fresh water. In Kazakhstan, irrigated farming takes more than sixty percent of all water withdrawals. We know what happens when that water is managed without data: the Aral Sea lost about ninety percent of its volume.

**[3 · Gap] — 25 s**
> Today the threat is faster. A flash drought can dry out a field in two to three weeks. Everyday forecasts see about ten days ahead. Science can already see these droughts a month ahead, but nobody delivers that to a farmer in Central Asia, in his language, in a form he can act on.

**[4 · Solution] — 20 s**
> AquaTwin closes that gap. It tracks the water balance, how much water the air takes and how much rain brings, against thirty years of climate. It scans fifty-one ECMWF forecast scenarios for the next six weeks and sends the farmer a short message on Telegram: the risk and what to do.

**[6 · MVP / live demo] — 40 s**
> Let me show you. This is a replay of real data: it is May 2021 and I'm a farmer in Maktaaral. *(send `/replay 2021-05-07 maktaaral`, bot answers)* High risk: the water deficit is a third above normal. Irrigate priority fields now, book your water turn today. Two weeks later the dry spell began and lasted sixty-one days. In Kazakh, Russian or English. And this is today, live *(send location)*. The same picture is on the district dashboard for the akimat.

**[Evidence slide] — 20 s**
> We checked thirty-five years of reanalysis for our eight districts. Our index ranks 2021, the drought year people here remember, as the driest season in three districts and the second driest in three more. Dry spells went from about 0.7 per district per season in the 1990s to 1.9 since 2011. The six-week forecast itself is not verified yet. That is our next step.

**[8 · NVIDIA] — 15 s**
> Today we work at district level, and we already show ECMWF's AI ensemble next to the physics-based one. With NVIDIA Earth-2 we want to run six-week AI ensembles ourselves, and later bring them down towards individual fields.

**[9–10 · Scale & ask] — 15 s**
> Farmers use it for free; water associations, akimats and insurers pay. We start in Kazakhstan's south and scale to every irrigated region. We're asking for compute, Earth-2 mentorship and pilot partners.

**[11 · Close] — 10 s**
> We come from the region that lost a sea. We're building AI so no one else does. Thank you.

> ⚠️ Цифры в тексте взяты из `reports/calibration.json` (ERA5, 8 районов, сезон апрель–сентябрь). Если отчёт пересчитан, сверить текст с ним. Нет цифры — убираем фразу, не придумываем.
> Фразу про «the drought year people here remember» оставить, только если сверка с новостями и сводками за 2021 год сделана (`VALIDATION_PLAN.md`, часть A.4).

### Произношение и подача
- Учить не дословно, а по ключевым фразам на слайд.
- Темп спокойный, паузы после чисел (70%, 60%, 90%).
- Один говорит, другой ведёт демо. Меняться ролями 1 раз (на демо).

---

## 2. Сценарий живого демо (40 секунд)

### Подготовка до выхода
- [ ] Телефон с Telegram, бот открыт, язык выбран **заранее** (English для жюри).
- [ ] Геолокация: заранее отправить себе точку в Мактаарале (40.67, 68.55) или использовать `/district maktaaral`.
- [ ] Команда повтора набрана заранее: `/replay 2021-05-07 maktaaral`.
- [ ] За 5 минут до выхода открыть дашборд и написать боту `/start`: бесплатные сервисы Render засыпают через 15 минут и просыпаются около минуты.
- [ ] Дашборд открыт во второй вкладке на районе Maktaaral.
- [ ] Экран телефона транслируется (AirPlay / scrcpy / камера над столом). Проверить на репетиции.

### Ход демо
1. «It is May 2021 and I'm a farmer in Maktaaral» → отправить `/replay 2021-05-07 maktaaral`.
2. Ответ пришёл → прочитать **только заголовок и первое действие**; сказать, что через две недели началась засуха на 61 день.
3. «And this is today, live» → отправить геолокацию. Пока бот считает (2–5 с): «It compares the last two weeks with thirty years of history and scans fifty-one forecast scenarios».
4. Переключиться на дашборд → показать карту и график района с коридором сценариев, 5 секунд.

В октябре–марте живой ответ помечен «вне поливного сезона» и советов по поливу не содержит. Поэтому показ начинается с повтора.

### Запасные планы (обязательно)
| Что сломалось | Что делаем |
|---|---|
| Нет интернета | бот с флагом `--replay` на ноутбуке и дашборд в режиме «Replay of the past»; сказать: «this is a replay of real 2021 data» |
| Сервис на Render спит | подождать минуту или запустить бота с ноутбука: `python bot.py` |
| Бот не отвечает | показать заранее записанное видео (1 мин) |
| Проектор не видит телефон | скриншоты на слайде 6 |
| Всё сломалось | продолжить по слайдам, демо = слайд 6 |

**Правило:** если демо не пошло за 10 секунд — сразу переходим к запасному плану, без извинений и отладки на сцене.

---

## 3. Видео-демо для заявки (1–2 минуты)

1. 0:00–0:10 — титр: «AquaTwin — flash-drought early warning».
2. 0:10–0:40 — запись экрана телефона: старт бота → выбор языка → геолокация → ответ.
3. 0:40–1:10 — запись дашборда: карта, выбор района, график, превью сообщения.
4. 1:10–1:30 — переключение языка на Қазақша, ответ бота на казахском.
5. Озвучка на английском (можно текстом из раздела 1) или субтитры.

Инструменты: встроенная запись экрана телефона, OBS / Loom для ПК. Формат MP4, до 100 MB (лимит формы).

---

## 4. Деплой (чтобы была ссылка, а не только ноутбук)

### 4.1. Код на GitHub
```bash
cd aquatwin
git init && git add . && git commit -m "AquaTwin MVP"
# создать пустой репозиторий на github.com, затем:
git remote add origin https://github.com/<user>/aquatwin.git
git push -u origin main
```
Токен бота **никогда** не коммитить: только переменная окружения.

### 4.2. Дашборд и бот → Render
Оба сервиса созданы 11.10.2026 на бесплатном тарифе и пересобираются при каждом пуше в ветку `main`:
- дашборд: `https://aquatwin-dashboard.onrender.com` — вставить в описание заявки и на слайд 6;
- бот: `@AquaTwin_Bot`, сервис `aquatwin-bot`. На Render он работает через webhook, локально — через polling.

Токен бота хранится только в переменной `TELEGRAM_TOKEN` в панели Render.

> Бесплатный сервис засыпает через 15 минут без запросов и просыпается около минуты. В день показа разбудить оба заранее или запустить бота с ноутбука.

---

## 5. Вопросы жюри (EN) — заготовки ответов

| Question | Answer |
|---|---|
| **Where is the AI?** | Today we show ECMWF's AI weather model, AIFS, next to the physics-based ensemble: fifty-one scenarios, two weeks ahead. We have not trained our own model yet. Next we want to run six-week AI ensembles ourselves on NVIDIA Earth-2, and for that we need GPUs. |
| **How accurate is it?** | We use ECMWF's ensemble and report a share of scenarios, not a certainty. Our index sees the known 2021 drought in history. We have not verified the six-week forecast against past forecasts yet; we started with what we could check honestly. |
| **How is this different from OpenET or commercial tools?** | They serve large farms with expensive infrastructure, mostly in the US and Europe. We serve smallholders in Central Asia: Telegram, local languages, no sensors, six-week horizon. |
| **Why would farmers trust it?** | The message tells them *why*: the water deficit in millimetres against the thirty-year normal, and how many forecast scenarios agree. The advice is not reviewed by an agronomist yet and we have not interviewed farmers yet; both are planned. |
| **Who pays?** | Farmers use it free. Water users' associations, akimats and agricultural insurers pay for planning tools and risk data. |
| **What if the forecast is wrong?** | We show risk levels, not certainties, and advice that is cheap to follow: irrigate earlier, book water. A false alarm costs little; a missed drought costs a harvest. |
| **Why you?** | We're from this region, we built a working MVP, and we're honest about its limits. |
| **What do you need from NVIDIA?** | GPU compute, Earth-2 mentorship and introductions to pilot partners. |

---

## 6. Чек-лист подачи формы (до 12.10)

**Требования конкурса:**
- [ ] Проект доведён до MVP → живой дашборд и бот, видео-демо.
- [ ] Свободный английский → питч отрепетирован минимум 3 раза вслух.
- [ ] Готовность приходить на репетиции → проверить расписание обоих.

**Поля формы:**
- [ ] ФИО
- [ ] Логин на платформе
- [ ] Презентация: экспорт в PDF (надёжнее, чем PPTX), до 100 MB, плейсхолдеры заменены
- [ ] Описание проекта: текст из чата + ссылка на дашборд + ссылка на GitHub + ссылка на видео
- [ ] Мотивационное письмо: текст из чата, цифры только реальные
- [ ] Telegram: свой ник

**Финальная проверка перед отправкой:**
- [ ] Нет квадратных скобок `[ ]` ни в слайдах, ни в текстах.
- [ ] Все цифры в слайдах есть в `reports/` или в источниках.
- [ ] Ссылки открываются в режиме инкогнито.
- [ ] Друг прочитал всё свежим взглядом.

---

## 7. Новые слайды после доработок

| Слайд | Что на нём | Откуда |
|---|---|---|
| **Evidence** (после MVP) | график `skill_by_horizon.png` + фраза case study | `ML_MODULE_SPEC.md`, `VALIDATION_PLAN.md` B |
| **Problem** (обновить) | «N flash droughts since 1991 in our pilot districts» + цитата фермера | `VALIDATION_PLAN.md` A, D |
| **MVP** (обновить) | реальные скриншоты, QR-код на бота и дашборд | деплой |
| **Team** (по желанию) | фото, роли, «why us» в одну строку | — |
