# Исправление: Обработка событий без condition_id

## Проблема

События без `condition_id` блокировали сигналы, потому что:
1. Код пропускал события без `condition_id` (строка 1069-1070)
2. Проверка `is_market_active()` требовала `condition_id`
3. События не обрабатывались, даже если были адреса кошельков

## Решение

### 1. Fallback идентификаторы для condition_id

Если `condition_id` отсутствует, используется fallback:
- `SLUG:{market_slug}` - если есть market slug
- `TITLE:{market_title[:50]}` - если есть market title

**Изменения:**
- `polymarket_notifier.py:1069-1088` - обработка без condition_id в `get_trades()`
- `polymarket_notifier.py:2700-2714` - обработка без conditionId в `monitor_wallets()`

### 2. Пропуск проверок для fallback condition_ids

Проверки `is_market_active()` и `has_traded_market()` пропускаются для fallback condition_ids (начинающихся с `SLUG:` или `TITLE:`).

**Изменения:**
- `polymarket_notifier.py:1477-1497` - пропуск проверок в `check_consensus_and_alert()`
- `polymarket_notifier.py:1537-1547` - пропуск проверки активности рынка
- `polymarket_notifier.py:2719-2723` - пропуск проверки в `monitor_wallets()`

### 3. Сохранение адресов кошельков

Адреса кошельков сохраняются в `alerts_sent` через:
- `wallets_csv` - список адресов через запятую
- `wallet_details_json` - детальная информация о кошельках

**Уже работает:**
- `polymarket_notifier.py:2504` - сохранение `wallets_csv`
- `polymarket_notifier.py:2494-2505` - сохранение `wallet_details_json`

## Результат

✅ **Сигналы будут приходить даже без condition_id**
- Используются fallback идентификаторы (SLUG: или TITLE:)
- Проверки активности рынка пропускаются для fallback IDs

✅ **Адреса кошельков сохраняются**
- `wallets_csv` содержит список адресов
- `wallet_details_json` содержит детальную информацию

✅ **MIN_TOTAL_POSITION_USD=$1000 остается без изменений**
- Порог $1000 сохранен как требовалось

## Как проверить

1. **Проверьте логи на сервере:**
   ```bash
   grep -i "SLUG:\|TITLE:" /opt/polymarket-bot/polymarket_notifier.log | tail -20
   ```

2. **Проверьте сохранение адресов:**
   ```sql
   SELECT condition_id, wallets_csv, wallet_count 
   FROM alerts_sent 
   WHERE condition_id LIKE 'SLUG:%' OR condition_id LIKE 'TITLE:%'
   ORDER BY sent_at DESC 
   LIMIT 10;
   ```

3. **Проверьте новые сигналы:**
   - Сигналы должны приходить даже без condition_id
   - Адреса кошельков должны сохраняться в `alerts_sent`

## Важные замечания

1. **Fallback condition_ids** (`SLUG:` или `TITLE:`) используются только для группировки событий
2. **Проверки активности рынка** пропускаются для fallback IDs, чтобы не блокировать сигналы
3. **Адреса кошельков** всегда сохраняются, независимо от наличия condition_id

