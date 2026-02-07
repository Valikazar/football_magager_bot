# ⚽ Football Manager: Bot & Site

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## 🌟 Project Overview (English)

This project is a comprehensive solution for organizing football matches, consisting of a Telegram bot and a companion website.

### 📁 Repository Structure
- **`footbot_site/`**: Web dashboard for statistics and match results using Node.js and Express.

### 🤖 Live Bot
You can use the official bot: **[@play_mygame_bot](https://t.me/play_mygame_bot)**

**How to start:**
1. Add **@play_mygame_bot** to your Telegram group.
2. Grant the bot administrative rights: **Delete Messages** (required for poll management).
3. Send `/poll` to create your first match registration.

### 🚀 Components

#### 1. Telegram Bot (`footbot_ tg_bot`)
- **Registration**: Players can sign up for matches with specific roles.
- **Team Balancing**: Smart algorithms to create fair teams based on player skills.
- **Stat Tracking**: Records goals, assists, and player ratings.
- **Admin Tools**: Manage players, edit stats, and configure match settings.

#### 2. Web Site (`footbot_site`)
- **Leaderboards**: View top players and their performance.
- **Match History**: Detailed results and event timelines for every match.
- **Player Stats**: Individual profiles with historical data.

### 🛠 Tech Stack
- **Bot**: Python 3.10+, Aiogram 3.x, MySQL.
- **Site**: Node.js, Express, EJS, MySQL.
- **Database**: Shared MySQL database.

---

<a name="русский"></a>
## 🌟 Обзор проекта (Русский)

Этот проект представляет собой комплексное решение для организации футбольных матчей, состоящее из Telegram-бота и сопутствующего веб-сайта.

### 📁 Структура репозитория
- **`footbot_site/`**: Веб-панель для просмотра статистики и результатов матчей на Node.js и Express.

### 🤖 Рабочий бот
Вы можете воспользоваться официальным ботом: **[@play_mygame_bot](https://t.me/play_mygame_bot)**

**Как начать:**
1. Добавьте **@play_mygame_bot** в вашу группу Telegram.
2. Дайте боту права администратора: **Удаление сообщений** (необходимо для управления постами записи).
3. Отправьте `/poll`, чтобы создать первый сбор на игру.

### 🚀 Компоненты

#### 1. Telegram-бот (`footbot_ tg_bot`)
- **Запись на матчи**: Регистрация игроков с выбором позиций.
- **Жеребьевка**: Умные алгоритмы для создания равных составов на основе рейтинга игроков.
- **Статистика**: Учет голов, ассистов и оценок за матч.
- **Админка**: Управление игроками, редактирование статов и настроек матча.

#### 2. Веб-сайт (`footbot_site`)
- **Таблицы лидеров**: Рейтинги лучших игроков.
- **История матчей**: Подробные результаты и хронология событий каждого матча.
- **Профили игроков**: Индивидуальная статистика и история выступлений.

### 🛠 Технологии
- **Бот**: Python 3.10+, Aiogram 3.x, MySQL.
- **Сайт**: Node.js, Express, EJS, MySQL.
- **База данных**: Общая база MySQL.

---

## 📄 License
MIT
