# Анализ блокировок сигналов

## Найденные проблемы

### 1. ⚠️ MIN_TOTAL_POSITION_USD = $1000.00

**Проблема:** Сигналы блокируются, если общая позиция (total_usd) меньше $1000.

**Где проверяется:**
- `polymarket_notifier.py`, строка 2283
- Значение по умолчанию: `1000.0` (если не установлено в .env)

**Решение:**
```bash
# В .env установите:
MIN_TOTAL_POSITION_USD=0
```

Или установите более низкое значение, например:
```bash
MIN_TOTAL_POSITION_USD=100
```

### 2. ⚠️ События без condition_id

**Проблема:** Все текущие события в `rolling_buys` не содержат `condition_id`, потому что:
- Бот не был перезапущен после исправления кода
- Старые события созданы до исправления

**Решение:**
1. Убедитесь, что код исправлен (добавлено сохранение `conditionId`, `outcomeIndex`, `side`)
2. Перезапустите бот на сервере:
   ```bash
   sudo systemctl restart polymarket-notifier
   ```

### 3. Все возможные блокировки сигналов

Сигналы блокируются в следующих случаях:

1. **Ниже порога кошельков** (`MIN_CONSENSUS`)
   - Код: `polymarket_notifier.py:1490`
   - Лог: `"BLOCKED: Below threshold"`

2. **Рынок неактивен/закрыт**
   - Код: `polymarket_notifier.py:1520, 1459`
   - Лог: `"BLOCKED: Market closed"`

3. **Алерт уже отправлен**
   - Код: `polymarket_notifier.py:1542`
   - Лог: `"BLOCKED: Alert already sent"`

4. **Расхождение цен входа**
   - Код: `polymarket_notifier.py:1618`
   - Лог: `"BLOCKED: Entry price divergence"`

5. **Рынок разрешен** (цена >= 0.999 или <= 0.001)
   - Код: `polymarket_notifier.py:1693`
   - Лог: `"BLOCKED: Market resolved"`

6. **Рынок закрыт** (цена >= 0.98 или <= 0.02)
   - Код: `polymarket_notifier.py:1730`
   - Лог: `"BLOCKED: Market closed"`

7. **Недостаточный размер позиции** (`MIN_TOTAL_POSITION_USD`)
   - Код: `polymarket_notifier.py:2283`
   - Лог: `"BLOCKED: Insufficient total position size"`

8. **Cooldown активен** (30 минут)
   - Код: `polymarket_notifier.py:2234`
   - Лог: `"BLOCKED: Cooldown"`

9. **Недавний противоположный сигнал**
   - Код: `polymarket_notifier.py:2251`
   - Лог: `"BLOCKED: Opposite side recent"`

10. **Нет триггера для повторного алерта**
    - Код: `polymarket_notifier.py:2205`
    - Лог: `"BLOCKED: no_trigger_matched"`

## Проверка на сервере

### Команды для проверки:

```bash
# 1. Проверка блокировок в логах
grep -i "BLOCKED\|blocked\|suppress" /opt/polymarket-bot/polymarket_notifier.log | tail -50

# 2. Статистика блокировок
grep -i "BLOCKED" /opt/polymarket-bot/polymarket_notifier.log | grep -oE "(below_threshold|market_inactive|price|cooldown|insufficient_position|no_trigger)" | sort | uniq -c | sort -rn

# 3. Проверка настроек
grep -E "MIN_CONSENSUS|ALERT_WINDOW_MIN|MIN_TOTAL_POSITION_USD" /opt/polymarket-bot/.env

# 4. Использование скрипта проверки
./check_server_blocks.sh
```

## Рекомендации

1. **Проверьте MIN_TOTAL_POSITION_USD**
   - Если установлено значение > 0, сигналы могут блокироваться
   - Рекомендуется: `MIN_TOTAL_POSITION_USD=0` или низкое значение (100-500)

2. **Перезапустите бот после исправления кода**
   ```bash
   sudo systemctl restart polymarket-notifier
   ```

3. **Проверьте логи на сервере**
   - Найдите конкретные причины блокировок
   - Проверьте, какие консенсусы блокируются и почему

4. **Мониторинг новых событий**
   - После перезапуска проверьте, что новые события содержат `conditionId`
   - Используйте скрипт `check_signal_blocks.py` для проверки

## Исправления в коде

✅ **Исправлено:** Добавлено сохранение `conditionId`, `outcomeIndex`, `side` в события `rolling_buys`
- Файл: `db.py`, строка 443-445
- Теперь все новые события будут содержать эту информацию

## Следующие шаги

1. Проверьте настройки на сервере
2. Перезапустите бот
3. Проверьте логи на наличие блокировок
4. Убедитесь, что новые события содержат `condition_id`

