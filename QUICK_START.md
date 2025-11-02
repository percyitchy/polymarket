# Быстрый старт после перезагрузки

## 📋 Текущая ситуация

1. ✅ Бот остановлен
2. ❌ HashDive API недоступен (502)
3. ❌ Google OAuth блокирует автоматизированные браузеры

## 🎯 Проблема с парсингом Insiders

Google блокирует Playwright/Firefox из-за детекта автоматизации.

### Решение: Undetected ChromeDriver

```bash
# Установить
pip install undetected-chromedriver

# Создать скрипт
nano hashdive_undetected.py
```

```python
import undetected_chromedriver as uc
from selenium import webdriver
from bs4 import BeautifulSoup
import time

driver = uc.Chrome()
driver.get("https://hashdive.com")

# Войти через Google (вручную)
print("Войдите через Google в браузере...")
time.sleep(60)

# Перейти на Insiders
driver.get("https://hashdive.com/Insiders")
time.sleep(5)

# Парсить данные
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Найти таблицы
tables = soup.find_all('table')
print(f"Found {len(tables)} tables")

driver.quit()
```

## 📞 Контакты

**HashDive Support**: contact@hashdive.com  
**API Key**: 2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c

## 📁 Важные файлы

- `hashdive_client.py` - готовый API клиент
- `PROJECT_STATUS.md` - полный статус проекта
- Все скрипты в директории

## ⚡ Быстрая команда

После перезагрузки:
```bash
cat PROJECT_STATUS.md
```

---

**Проблема**: Google OAuth блокирует автоматизацию  
**Решение**: undetected-chromedriver или ручной парсинг


