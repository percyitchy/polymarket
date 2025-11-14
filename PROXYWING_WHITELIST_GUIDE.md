# Инструкция: Добавление IP в Whitelist ProxyWing

## IP адрес сервера для добавления:
```
YOUR_SERVER_IP
```

## Пошаговая инструкция:

### Шаг 1: Вход в личный кабинет
1. Перейдите на сайт ProxyWing: https://proxywing.com
2. Войдите в свой аккаунт

### Шаг 2: Поиск раздела Whitelist
В личном кабинете найдите один из следующих разделов:
- **"IP Whitelist"** или **"Whitelist"**
- **"Security"** → **"IP Whitelist"**
- **"Settings"** → **"Access Control"** → **"IP Whitelist"**
- **"Dashboard"** → **"Whitelist"**

### Шаг 3: Добавление IP адреса
1. Нажмите кнопку **"Add IP"** или **"Add to Whitelist"**
2. Введите IP адрес: `YOUR_SERVER_IP`
3. (Опционально) Добавьте описание: `Polymarket Bot Server`
4. Нажмите **"Save"** или **"Add"**

### Шаг 4: Проверка
1. Убедитесь, что IP `YOUR_SERVER_IP` появился в списке разрешенных IP
2. Статус должен быть **"Active"** или **"Enabled"**

## Альтернативные варианты (если Whitelist недоступен):

### Вариант 1: Проверка настроек прокси
Если в ProxyWing нет функции whitelist, возможно:
- Прокси уже настроены на работу без whitelist
- Требуется другой тип прокси (например, с авторизацией по username/password)

### Вариант 2: Обращение в поддержку
Если не можете найти раздел whitelist:
1. Напишите в поддержку ProxyWing
2. Укажите IP адрес: `YOUR_SERVER_IP`
3. Попросите добавить его в whitelist для ваших прокси

### Вариант 3: Использование прокси без whitelist
Если whitelist недоступен, убедитесь что:
- Прокси используют авторизацию по username/password (уже настроено)
- Формат прокси правильный: `socks5://username:password@domain:port`

## Проверка работы прокси после добавления в whitelist:

После добавления IP в whitelist, проверьте работу прокси:

```bash
# На сервере выполните:
cd /opt/polymarket-bot
python3 -c "
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

proxy = {
    'http': 'socks5://pkg-private2-pool-onlyipv4-session-Jt1WkY8S:nenbaisd31wsawmw@quality.proxywing.com:1080',
    'https': 'socks5://pkg-private2-pool-onlyipv4-session-Jt1WkY8S:nenbaisd31wsawmw@quality.proxywing.com:1080'
}

try:
    response = requests.get('https://clob.polymarket.com/markets', proxies=proxy, timeout=10, verify=False)
    print(f'✅ Прокси работает! Статус: {response.status_code}')
except Exception as e:
    print(f'❌ Ошибка: {e}')
"
```

## Важные замечания:

1. **Время активации**: Изменения в whitelist могут вступить в силу через несколько минут
2. **Fallback механизм**: Бот автоматически переключится на прямое подключение, если прокси не работают
3. **Мониторинг**: После добавления IP проверьте логи бота на наличие ошибок прокси

## Контакты поддержки ProxyWing:

Если возникли проблемы:
- Email: support@proxywing.com (проверьте на сайте)
- Live Chat: доступен в личном кабинете
- Документация: https://proxywing.com/docs (если доступна)
