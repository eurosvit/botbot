# BotBot - Автоматизований бот для аналізу продажів і оптимізації конверсій

Автоматизований бот, який зводить дані з різних сервісів (Google Ads, Microsoft Clarity, Sales Drive CRM), аналізує продажі, трафік, витрати та знаходить слабкі місця для покращення конверсії на сайті, оптимізації реклами та фіда товарів. Щодня зранку надсилає звіт в Telegram за минулий день та список задач на покращення.

## 🚀 Функціональність

- **Інтеграція з Google Ads** - аналіз ефективності рекламних кампаній
- **Інтеграція з Microsoft Clarity** - аналіз поведінки користувачів на сайті  
- **Інтеграція з Sales Drive CRM** - обробка даних про замовлення
- **Щоденні звіти в Telegram** - автоматичне надсилання звітів щоранку
- **Генерація actionable insights** - конкретні рекомендації для покращення
- **Аналіз ROAS і рентабельності** - розрахунок ключових метрик
- **Автоматичне планування завдань** - розклад на основі APScheduler

## 📋 Налаштування

### Змінні середовища

Створіть файл `.env` у кореневій директорії:

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Telegram Bot
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_telegram_chat_id

# Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
GOOGLE_ADS_CLIENT_ID=your_client_id
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_login_customer_id
GOOGLE_ADS_CUSTOMER_ID=your_customer_id

# Microsoft Clarity
CLARITY_TOKEN=your_clarity_api_token

# Other
TZ=Europe/Kyiv
ENABLE_SCHEDULER=true
DAILY_REPORT_CRON=0 8 * * *

# E-commerce settings
BRAND_MARGINS_UAH={"brand1": "0.3", "brand2": "0.25"}
DEFAULT_MARGIN_UAH=0.3
```

### Встановлення залежностей

```bash
pip install -r requirements.txt
```

## 🏃‍♂️ Запуск

### Локальний розробницький режим
```bash
python app/main.py
```

### Продакшн режим
```bash
gunicorn app.main:app
```

## 📊 API Endpoints

### `GET /daily_report`
Генерує та надсилає щоденний звіт

### `POST /webhooks/salesdrive`
Webhook для отримання даних з Sales Drive CRM

### `GET /healthz`
Перевірка здоров'я сервісу

## 🕐 Автоматичні завдання

Бот автоматично надсилає щоденні звіти о 8:00 ранку (за замовчуванням). Час можна налаштувати через змінну `DAILY_REPORT_CRON`.

## 📈 Аналітика та рекомендації

Бот аналізує:
- ROAS (Return on Ad Spend)
- Рентабельність продажів
- Конверсію замовлень
- Поведінку користувачів на сайті
- Ефективність рекламних кампаній

І надає actionable рекомендації:
- Оптимізація рекламних кампаній
- Покращення UX/UI сайту
- Налаштування A/B тестів
- Аналіз слабких місць конверсії

## 🔧 Режим розробки

У разі відсутності налаштувань для зовнішніх сервісів, бот використовує mock дані для тестування функціональності.

## 📝 Логування

Всі операції логуються з використанням стандартного модуля logging Python. Рівень логування можна налаштувати через конфігурацію.

## 🚀 Deployment

Проект готовий для розгортання на Heroku, Render та інших PaaS платформах. Файл `Procfile` вже налаштований.
