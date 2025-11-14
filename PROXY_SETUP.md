# Proxy Configuration для Polymarket API

## Зачем нужны прокси?

При большом количестве параллельных запросов с одного IP адреса Polymarket может применять Rate Limiting (429 ошибки). Использование прокси с ротацией IP позволяет:

- ✅ Распределить нагрузку по разным IP адресам
- ✅ Обойти лимиты на один IP
- ✅ Увеличить пропускную способность обработки кошельков
- ✅ Снизить количество Rate Limit ошибок

## Настройка прокси

### 1. Добавьте прокси в `.env` файл:

```bash
# Формат: через запятую, без пробелов
POLYMARKET_PROXIES=http://user:pass@proxy1.com:8080,http://user:pass@proxy2.com:8080,socks5://user:pass@proxy3.com:1080
```

### 2. Форматы прокси:

- **HTTP**: `http://username:password@host:port`
- **SOCKS5**: `socks5://username:password@host:port`
- **Без авторизации**: `http://host:port`

### 3. Примеры провайдеров прокси:

- **Bright Data** (Luminati): `http://customer-USERNAME:PASSWORD@zproxy.lum-superproxy.io:22225`
- **Smartproxy**: `http://USERNAME:PASSWORD@gate.smartproxy.com:7000`
- **ProxyMesh**: `http://USERNAME:PASSWORD@us-wa.proxymesh.com:31280`
- **Residential прокси**: обычно дороже, но более надежные

### 4. Рекомендации:

- Используйте минимум **3-5 прокси** для ротации
- Предпочтительны **residential прокси** (выглядят как обычные пользователи)
- Проверьте, что прокси поддерживают HTTPS
- Убедитесь, что прокси не заблокированы Polymarket

## Как работает ротация?

1. Каждый запрос использует следующий прокси из списка (round-robin)
2. При Rate Limit (429) прокси автоматически ротируется
3. Неисправные прокси временно исключаются из ротации
4. Если все прокси недоступны, используется прямое подключение

## Мониторинг

Проверьте логи на наличие сообщений:
- `✅ Proxy manager initialized with X proxies` - прокси загружены
- `Rotating proxy for retry` - прокси ротируется при ошибке
- `⚠️ Proxy list is empty` - прокси не настроены, используется прямое подключение

## Без прокси

Если прокси не настроены (`POLYMARKET_PROXIES` не указан), бот работает как раньше - с прямым подключением с одного IP адреса.

