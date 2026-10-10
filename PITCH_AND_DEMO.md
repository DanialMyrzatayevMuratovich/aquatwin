# AquaTwin — питч, демо, деплой и подача заявки

> Всё, что нужно для сцены: текст выступления на английском, сценарий живого демо с запасными планами,
> деплой, ответы на вопросы и чек-лист подачи формы.

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
> AquaTwin closes that gap. It monitors soil moisture against thirty years of climate, scans a 46-day forecast for flash-drought onset, and sends the farmer a short message on Telegram: the risk and what to do.

**[6 · MVP / live demo] — 40 s**
> Let me show you. I'm a farmer in Maktaaral. I send my location… *(bot answers)* High risk, drought expected in about [X] days, irrigate priority fields now, book your water turn today. In Kazakh, Russian or English. The same picture is on the district dashboard for the akimat.

**[Evidence slide, после ML и валидации] — 20 s**
> We trained our own model on 35 years of data. On unseen years 2020 to 2025 it beats the baseline by [X]% at three weeks. In [month, year] in [district] it would have raised the alarm [X] days before the drought started.

**[8 · NVIDIA] — 15 s**
> Today we work at district level. With NVIDIA Earth-2 we can downscale AI weather ensembles to individual fields.

**[9–10 · Scale & ask] — 15 s**
> Farmers use it for free; water associations, akimats and insurers pay. We start in Kazakhstan's south and scale to every irrigated region. We're asking for compute, Earth-2 mentorship and pilot partners.

**[11 · Close] — 10 s**
> We come from the region that lost a sea. We're building AI so no one else does. Thank you.

> ⚠️ Квадратные скобки [X] заполняем **только реальными цифрами** из `reports/metrics.json` и case study. Нет цифры — убираем фразу, не придумываем.

### Произношение и подача
- Учить не дословно, а по ключевым фразам на слайд.
- Темп спокойный, паузы после чисел (70%, 60%, 90%).
- Один говорит, другой ведёт демо. Меняться ролями 1 раз (на демо).

---

## 2. Сценарий живого демо (40 секунд)

### Подготовка до выхода
- [ ] Телефон с Telegram, бот открыт, язык выбран **заранее** (English для жюри).
- [ ] Геолокация: заранее отправить себе точку в Мактаарале (40.67, 68.55) или использовать `/district maktaaral`.
- [ ] Дашборд открыт во второй вкладке на районе Maktaaral.
- [ ] Экран телефона транслируется (AirPlay / scrcpy / камера над столом). Проверить на репетиции.

### Ход демо
1. «I'm a farmer in Maktaaral» → отправить геолокацию (или `/district maktaaral`).
2. Пока бот считает (2–5 с): «It compares today's soil with thirty years of history and scans the next 46 days».
3. Ответ пришёл → прочитать **только заголовок и первое действие**.
4. Переключиться на дашборд → показать карту и график района, 5 секунд.

### Запасные планы (обязательно)
| Что сломалось | Что делаем |
|---|---|
| Нет интернета | бот с флагом `--demo` и дашборд с переключателем Demo data; сказать: «running on cached data» |
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

### 4.2. Дашборд → Streamlit Community Cloud
1. share.streamlit.io → New app → выбрать репозиторий, ветку `main`, файл `app.py`.
2. Python-версию и зависимости он возьмёт из `requirements.txt`.
3. Получится публичная ссылка вида `https://<name>.streamlit.app`. Вставить её в описание заявки и на слайд 6.

### 4.3. Бот → любой хостинг с фоновым процессом
Варианты: Render (Background Worker), Railway, Fly.io, любой VPS.
- Команда запуска: `python bot.py`
- Переменная окружения: `TELEGRAM_TOKEN=<токен>`
- Бот работает в режиме polling, публичный адрес и вебхук не нужны.
- Проверить: после деплоя написать боту `/start` с другого телефона.

> Условия бесплатных тарифов у хостингов меняются. Проверьте на их сайте, не «засыпает» ли процесс на бесплатном плане. Для конкурса надёжнее запустить бота на ноутбуке или VPS на время показа.

---

## 5. Вопросы жюри (EN) — заготовки ответов

| Question | Answer |
|---|---|
| **Where is the AI?** | Two layers: ECMWF's ensemble forecast, and our own gradient-boosting model trained on 35 years of soil and weather data that predicts flash-drought probability 4 weeks ahead. On unseen years it beats the baseline by [X]%. |
| **How accurate is it?** | At three weeks our model is [X]% better than persistence on 2020–2025 data. Accuracy drops after about a month; that's exactly where Earth-2 ensembles help. |
| **How is this different from OpenET or commercial tools?** | They serve large farms with expensive infrastructure, mostly in the US and Europe. We serve smallholders in Central Asia: Telegram, local languages, no sensors, six-week horizon. |
| **Why would farmers trust it?** | We tested the advice with an agronomist and talked to [N] farmers. [Quote]. And the message tells them *why*: how dry the soil is compared to 30 years of history. |
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
