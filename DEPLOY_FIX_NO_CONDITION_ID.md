# Инструкция по развертыванию исправлений на сервере

## Шаги для обновления и перезапуска бота

### 1. Подключитесь к серверу
```bash
ssh your_user@your_server
```

### 2. Перейдите в директорию проекта
```bash
cd /opt/polymarket-bot
```

### 3. Создайте резервную копию текущей версии (опционально, но рекомендуется)
```bash
cp polymarket_notifier.py polymarket_notifier.py.backup.$(date +%Y%m%d_%H%M%S)
```

### 4. Обновите файл polymarket_notifier.py

**Вариант A: Если используете git:**
```bash
git pull origin main
# или
git pull origin master
```

**Вариант B: Если копируете файл вручную:**
```bash
# Скопируйте обновленный файл polymarket_notifier.py с локальной машины на сервер
# Используйте scp или другой метод копирования
scp /Users/johnbravo/polymarket/polymarket_notifier.py your_user@your_server:/opt/polymarket-bot/
```

### 5. Проверьте, что файл обновлен
```bash
# Проверьте наличие новых изменений (fallback для condition_id)
grep -n "SLUG:\|TITLE:" polymarket_notifier.py | head -5
```

Должны увидеть строки с обработкой fallback идентификаторов.

### 6. Перезапустите бота
```bash
sudo systemctl restart polymarket-notifier
```

### 7. Проверьте статус бота
```bash
sudo systemctl status polymarket-notifier
```

Должен показать `active (running)`.

### 8. Проверьте логи на наличие новых изменений
```bash
# Проверьте последние логи
tail -50 /opt/polymarket-bot/polymarket_notifier.log

# Проверьте, что бот обрабатывает события без condition_id
grep -i "SLUG:\|TITLE:" /opt/polymarket-bot/polymarket_notifier.log | tail -20
```

### 9. Мониторинг работы

Проверьте, что:
- Бот запущен и работает
- События обрабатываются (даже без condition_id)
- Сигналы приходят
- Адреса кошельков сохраняются в alerts_sent

```bash
# Проверка последних событий
tail -100 /opt/polymarket-bot/polymarket_notifier.log | grep -i "CONSENSUS\|SLUG:\|TITLE:"

# Проверка сохранения адресов в БД
sqlite3 /opt/polymarket-bot/polymarket_notifier.db "SELECT condition_id, wallets_csv, wallet_count FROM alerts_sent ORDER BY sent_at DESC LIMIT 5;"
```

## Откат изменений (если что-то пошло не так)

Если возникнут проблемы, можно откатиться к предыдущей версии:

```bash
# Найдите резервную копию
ls -la /opt/polymarket-bot/polymarket_notifier.py.backup*

# Восстановите из резервной копии
cp polymarket_notifier.py.backup.YYYYMMDD_HHMMSS polymarket_notifier.py

# Перезапустите бота
sudo systemctl restart polymarket-notifier
```

## Важные замечания

1. **Перед обновлением** убедитесь, что понимаете изменения
2. **Создайте резервную копию** перед обновлением
3. **Проверьте логи** после перезапуска
4. **Мониторьте работу** бота в течение первых часов после обновления

## Что изменилось

- Разрешена обработка событий без `condition_id`
- Используются fallback идентификаторы (`SLUG:` или `TITLE:`)
- Проверки активности рынка пропускаются для fallback IDs
- Адреса кошельков сохраняются в `alerts_sent`

