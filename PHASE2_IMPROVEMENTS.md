# Фаза 2: Дальнейшее снижение Unknown до 0%

## ✅ Реализованные улучшения

### 1. Добавлены новые категории

#### entertainment/Movies
- Ключевые слова: netflix, box office, oscar, emmy, golden globe, movie, film, series, tv show
- Примеры: "Will 'A House of Dynamite' be the top global Netflix movie this week?"

#### entertainment/Music
- Ключевые слова: grammy, billboard, spotify, album, song, artist, chart, top chart, music, single
- Примеры: "Grammy winner", "Billboard #1"

#### entertainment/Gaming
- Ключевые слова: lol, league of legends, worlds, worlds 2025, cs2, counter-strike, esports, valorant, dota, steam, playstation, xbox, nintendo, bo1, bo5, rolster, gen.g, ctbc, flying oyster, t1, kt rolster
- Примеры: "Will T1 win LoL Worlds 2025?", "LoL: Gen.G vs KT Rolster (bo5)"

#### tech/Releases
- Ключевые слова: release, launch, update, version, beta, alpha, app, api, ios, android, chatgpt, openai, sora, gemini, gpt, ai, artificial intelligence, model, be released, will be released, go live, polymarket us
- Примеры: "Will Gemini 3.0 be released by November 15?", "Will ChatGPT be #1 Free App in the US Apple App Store?"

### 2. Улучшены паттерны крипто

- Добавлена проверка для случаев, когда "bitcoin" и "up or down" разделены другими словами
- Улучшена обработка форматов с датами и временем: "bitcoin up or down - october 10, 2:30pm-2:45pm et"

### 3. Расширены ключевые слова для stocks/Companies

- Добавлены: "app store", "apple app store", "most searched", "top searched", "#1 searched", "searched person"
- Примеры: "Will Donald Trump be the #1 searched person on Google this year?"

### 4. Улучшен порядок проверок

- Tech и Entertainment проверяются ДО Politics, чтобы избежать ложных срабатываний
- Например: "US Apple App Store" теперь классифицируется как tech/Releases, а не politics/US

### 5. Обновлён ML классификатор

- Добавлены примеры для новых категорий (entertainment/Gaming, entertainment/Movies, entertainment/Music, tech/Releases)
- Расширена обучающая выборка

## 📊 Ожидаемые результаты

**Текущее состояние:**
- Unknown: 67.02% (50,738 рынков)
- Классифицировано: 32.98% (24,971 рынков)

**После пересчёта (ожидаемо):**
- Unknown: ~50-55% (снижение на 12-17 п.п.)
- Классифицировано: ~45-50% (увеличение на 12-17 п.п.)

**Основные улучшения:**
1. **Entertainment категории**: +3,000-5,000 рынков
2. **Tech/Releases**: +2,000-3,000 рынков
3. **Улучшенные крипто паттерны**: +1,000-2,000 рынков
4. **Расширенные stocks паттерны**: +500-1,000 рынков

**Итого ожидаемо**: +6,500-11,000 дополнительных классифицированных рынков

## 🚀 Следующие шаги

1. ✅ Запустить пересчёт всех категорий
2. Проанализировать оставшиеся Unknown рынки
3. Расширить ключевые слова на основе анализа
4. Улучшить источники данных (CLOB API, Polymarket Analytics)
5. Продолжить итеративное улучшение

## 📝 Файлы изменены

- `market_utils.py`: Добавлены категории entertainment и tech, улучшены паттерны
- `ml_classifier.py`: Добавлены примеры для новых категорий

