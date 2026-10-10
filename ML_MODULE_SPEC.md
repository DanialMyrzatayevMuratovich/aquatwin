# AquaTwin — ТЗ на ML-модуль («где здесь AI?»)

> Цель: добавить в MVP **собственную обученную модель** с честной метрикой против базовых линий.
> Оценка времени: 4–6 часов. Исполнитель: [Имя 1].
> Связанные файлы: `aquatwin/ml.py` (новый), `scripts/train.py` (новый), `app.py` (доработка).

---

## 1. Зачем

Сейчас прогноз = физическая модель ECMWF + пороговые правила. Своего машинного обучения нет.
Для заявки в NVIDIA нужен ответ на вопрос «где AI?» **с цифрой**, например:

> «Наша модель, обученная на 35 годах спутниковых и реанализных данных, предсказывает засуху на 3 недели вперёд на **X%** точнее, чем базовая линия».

X мы не знаем заранее. Пишем на слайд **только то, что покажут тесты**.

---

## 2. Постановка задачи

Две задачи, обе на одних и тех же признаках:

| Задача | Тип | Цель (target) | Горизонты |
|---|---|---|---|
| **A. Прогноз перцентиля** | регрессия | перцентиль влажности 7–28 см через *h* дней | h = 14, 21, 28 |
| **B. Риск внезапной засухи** | классификация | 1, если в ближайшие 28 дней начнётся flash drought (определение из `drought.detect_onset`) | 28 дней |

Задача B — главная для продукта: она прямо даёт «вероятность засухи в ближайшие 4 недели».

---

## 3. Данные

### 3.1. Источник
Open-Meteo Archive API (`https://archive-api.open-meteo.com/v1/archive`), модель `era5_land`, период **1991-01-01 … 2025-12-31**, daily.

| Переменная (daily) | Зачем |
|---|---|
| `soil_moisture_0_to_7cm_mean` | верхний слой, быстро реагирует |
| `soil_moisture_7_to_28cm_mean` | корневой слой (основной сигнал) |
| `soil_moisture_28_to_100cm_mean` | глубокий запас влаги |
| `precipitation_sum` | осадки |
| `et0_fao_evapotranspiration` | испаряемость |
| `temperature_2m_max` | жара |

> ⚠️ По таблице в документации Open-Meteo, в ERA5-Land нет осадков (температура, влажность почвы и ET0 есть). Поэтому `precipitation_sum` берите отдельным запросом с моделью `era5` (или `era5_seamless`) и склейте по дате.

### 3.2. Точки
- **Минимум:** 8 пилотных районов (`config.REGIONS`).
- **Лучше:** сетка ~40–60 точек по югу Казахстана и Узбекистану (шаг 0.5°) → больше примеров засух, и модель учится обобщать. Это же даёт аргумент масштабируемости: «модель работает на любой точке региона».

### 3.3. Объём
8 точек × 35 лет × 365 дней ≈ 100 тыс. строк; сетка 50 точек ≈ 640 тыс. строк. Помещается в память ноутбука.

### 3.4. Кэш
Сырые ответы сохранять в `data_cache/raw_<lat>_<lon>.parquet` (или `.csv`), чтобы не скачивать повторно.

---

## 4. Признаки (features) на день *t*

Все признаки считаются **только из прошлого** (≤ t), иначе будет утечка.

| Группа | Признаки |
|---|---|
| Состояние почвы | перцентиль 0–7, 7–28, 28–100 см на день t |
| Динамика | изменение перцентиля 7–28 см за 7, 14, 30 дней |
| Осадки | сумма за 7, 30, 60, 90 дней; аномалия к норме того же сезона |
| Испаряемость | сумма ET0 за 7 и 30 дней; баланс `P − ET0` за 30 и 60 дней |
| Жара | средний `temperature_2m_max` за 7 дней; число дней > 35 °C за 14 дней |
| Сезон | `sin(2π·doy/365)`, `cos(2π·doy/365)` |
| Место | широта, долгота, высота (из ответа API) |

Перцентили для признаков считать **по климатологии только из обучающих лет** (см. раздел 5), иначе утечка.

---

## 5. Разбиение и защита от утечек

**Только по времени, без перемешивания:**

| Набор | Годы | Зачем |
|---|---|---|
| train | 1991–2014 | обучение |
| validation | 2015–2019 | подбор гиперпараметров и порога |
| test | 2020–2025 | **финальная цифра на слайд**, смотрим один раз |

- Климатология (нормы для перцентилей) — только из train-лет.
- Цель на горизонте *h* смотрит в будущее, поэтому последние *h* дней каждого набора выбрасываем (gap), чтобы цель не залезала в следующий набор.

---

## 6. Модели

| Модель | Роль |
|---|---|
| **Persistence** — «через h дней перцентиль будет как сегодня» | базовая линия 1 |
| **Climatology** — «через h дней будет медиана нормы» / для B: частота засух в этот сезон | базовая линия 2 |
| **HistGradientBoosting** (scikit-learn) | основная модель |
| *(опционально)* XGBoost / LightGBM на GPU | для слайда «готовы к ускорению на NVIDIA» |

Начать с `sklearn.ensemble.HistGradientBoostingRegressor` / `...Classifier`: без новых зависимостей, быстро, работает с пропусками.

Стартовые гиперпараметры: `max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, early_stopping=True`. Для B: `class_weight="balanced"` (засух мало).

---

## 7. Метрики

### Задача A (регрессия)
- **MAE** перцентиля на test для h = 14, 21, 28.
- **Skill score** = `1 − MAE_model / MAE_persistence`. Это главная цифра: «на X% лучше базовой линии».

### Задача B (классификация)
- **ROC AUC** и **PR AUC** (PR AUC важнее, потому что событий мало).
- **Brier score** против климатологической частоты → Brier Skill Score.
- При выбранном пороге (подобрать на validation): **hit rate** (доля пойманных засух) и **false alarm ratio**.
- **Lead time:** за сколько дней до начала модель впервые подняла риск выше порога (медиана по событиям test).

### Отчёт
`scripts/train.py` сохраняет:
- `reports/metrics.json` — все цифры;
- `reports/skill_by_horizon.png` — столбцы MAE: persistence / climatology / model для 14/21/28 дней;
- `reports/feature_importance.png` — permutation importance (топ-10);
- `models/fd_classifier.joblib`, `models/pct_regressor_h21.joblib`.

---

## 8. Интеграция в продукт

1. `aquatwin/ml.py`:
   ```python
   def build_features(daily: pd.DataFrame, clim: dict) -> pd.DataFrame: ...
   def load_models(path="models/") -> dict: ...
   def predict_risk(features_today: pd.Series, models: dict) -> dict:
       # {"p_flash_drought_28d": 0.63, "pct_h14": 31.2, "pct_h21": 24.5, "pct_h28": 19.8}
   ```
2. `drought.assess()` получает необязательный аргумент `ml_result` и учитывает его так:
   - `high`, если **EC46 нашёл начало засухи** ИЛИ `p_flash_drought_28d ≥ порога` (порог из validation);
   - в `Assessment` добавить поле `p_ml` (вероятность от модели).
3. `advice.message()` добавляет строку: «AI-вероятность засухи в ближайшие 4 недели: 63%».
4. `app.py`: на графике района — точки ML-прогноза на 14/21/28 дней поверх линии EC46, плюс отдельный блок «Model skill» с цифрами из `reports/metrics.json`.
5. Если моделей нет на диске → всё работает как раньше (без ML), с пометкой.

Итог для питча: **гибрид «физика ECMWF + наш ML на 35 годах данных»**. Это честный и сильный ответ на «где AI».

---

## 9. Скелет обучения (`scripts/train.py`)

```python
"""python scripts/train.py --points config   (или --grid)"""
import json, pathlib
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import mean_absolute_error, roc_auc_score, average_precision_score, brier_score_loss
from aquatwin import ml

TRAIN, VAL, TEST = (1991, 2014), (2015, 2019), (2020, 2025)

df = ml.load_or_download_all_points()          # daily, все точки, все переменные
clim = ml.fit_climatology(df, years=TRAIN)      # нормы только из train
X, y_reg, y_cls = ml.make_dataset(df, clim, horizons=(14, 21, 28))

def split(frame, years):
    m = frame.index.get_level_values("date").year.isin(range(years[0], years[1] + 1))
    return frame[m]

report = {}
for h in (14, 21, 28):
    Xtr, ytr = split(X, TRAIN), split(y_reg[h], TRAIN)
    Xte, yte = split(X, TEST), split(y_reg[h], TEST)
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, early_stopping=True).fit(Xtr, ytr)
    mae_model = mean_absolute_error(yte, model.predict(Xte))
    mae_pers = mean_absolute_error(yte, Xte["pct_7_28"])
    report[f"h{h}"] = {"mae_model": mae_model, "mae_persistence": mae_pers,
                       "skill_vs_persistence": 1 - mae_model / mae_pers}

clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, class_weight="balanced")
clf.fit(split(X, TRAIN), split(y_cls, TRAIN))
p = clf.predict_proba(split(X, TEST))[:, 1]
yt = split(y_cls, TEST)
base = split(y_cls, TRAIN).mean()
report["flash_drought_28d"] = {
    "roc_auc": roc_auc_score(yt, p), "pr_auc": average_precision_score(yt, p),
    "brier": brier_score_loss(yt, p), "brier_climatology": brier_score_loss(yt, np.full_like(p, base)),
    "event_rate_test": float(yt.mean()),
}
pathlib.Path("reports").mkdir(exist_ok=True)
json.dump(report, open("reports/metrics.json", "w"), indent=2)
```

---

## 10. Тесты для ML

- `test_no_leakage`: признаки дня *t* не меняются, если обрезать данные после *t*.
- `test_split_disjoint`: train / val / test не пересекаются по датам.
- `test_predict_shape`: `predict_risk` возвращает вероятность в [0, 1] и три перцентиля.
- `test_fallback_without_models`: без файлов моделей `assess()` работает как раньше.

---

## 11. Правила честности (обязательно)

- На слайд — **только цифры test-набора** (2020–2025), посчитанные один раз.
- Если модель **не** лучше persistence на каком-то горизонте — так и пишем («на 14 днях выигрыш X%, на 28 — модель пока не лучше базовой линии»). Жюри доверяет честным графикам больше, чем идеальным.
- Не называть это «нашей моделью погоды». Это **модель засухи поверх реанализа и прогноза ECMWF**.

---

## 12. Definition of Done

- [ ] `python scripts/train.py` проходит от начала до конца и создаёт `reports/` и `models/`.
- [ ] В `reports/metrics.json` есть skill vs persistence для 14/21/28 и метрики классификатора.
- [ ] Дашборд показывает ML-вероятность и блок Model skill.
- [ ] Бот добавляет строку с AI-вероятностью.
- [ ] 4 новых теста проходят.
- [ ] Обновлён слайд 7 (Method) и добавлен слайд с графиком `skill_by_horizon.png`.
