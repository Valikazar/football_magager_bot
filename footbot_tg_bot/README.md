# ⚽ Play My Game: Football Match Manager

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## 🌟 Overview (English)

**Play My Game** is a powerful and flexible Telegram bot designed to automate football match organization. It handles everything from registration and queue management to intelligent team balancing based on player skills and historical match data.

### 🚀 Key Features

#### 📋 Registration Management
*   **Flexible Positions**: Players sign up for specific roles (Forward, Defender, Goalkeeper).
*   **Smart Queue**: Automatically handles "extra" players by creating a waiting list.
*   **Squad Limits**: Customizable player limits for every match.

#### ⚖️ Intelligent Draft (Team Balancing)
*   **Skill-Based Balancing**: An algorithm distributes players to ensure teams are as even as possible.
*   **Position Awareness**: Ensures goalkeepers and defenders are distributed fairly between teams.
*   **Multiple Modes**: Supports random draft or strictly stats-based balancing.

#### 📊 Stats & Profiles
*   **Player Ratings**: Personal attributes (Attack, Defense, Speed, GK) that influence the draft.
*   **Match History**: Records scores, goalscorers, and assists.
*   **Leaderboard**: A visual ranking of players within your community.

#### 💳 Finance & Administration
*   **Payment Tracking**: Mark players who have paid their fees and send reminders.
*   **Multi-language**: Full support for English and Russian.
*   **Admin Panel**: Manage chat settings, edit player stats, and create "Legionnaires" (players without Telegram).

---

## 📸 Screenshots

| Match Poll | Team Draft | Player Profile |
| :---: | :---: | :---: |
| ![Poll Screenshot](https://via.placeholder.com/300x500?text=Match+Poll+Screenshot) | ![Draft Screenshot](https://via.placeholder.com/300x500?text=Team+Draft+Screenshot) | ![Stats Screenshot](https://via.placeholder.com/300x500?text=Player+Stats+Screenshot) |
| *Example registration poll* | *Balancing result* | *Attribute viewer* |

---

## 🛠 Tech Stack

*   **Language**: Python 3.10+
*   **Bot Framework**: [Aiogram 3.x](https://docs.aiogram.dev/)
*   **Database**: MySQL
*   **Environment**: Dotenv
*   **Deployment**: PowerShell (manage.ps1) + PM2 (optional)

---

## 🚀 Quick Start

1. **Clone & Setup**:
   ```bash
   git clone https://github.com/Valikazar/football_magager_bot.git
   cd play-my-game
   cp .env.example .env
   ```

2. **Configure**:
   Edit `.env` with your bot token and DB credentials.

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run**:
   ```bash
   python main.py
   ```

---

<a name="русский"></a>
## 🌟 Обзор (Русский)

**Play My Game** — это мощный и гибкий Telegram-бот для автоматизации футбольных матчей. Он берет на себя всю рутину: от сбора состава и очередей до умного распределения команд по рейтингу и ведения статистики.

### � Управление записью
*   **Гибкие позиции**: Игроки записываются на конкретные роли (Нападающий, Защитник, Вратарь).
*   **Умная очередь**: Автоматическая обработка "лишних" игроков и создание листа ожидания.
*   **Лимиты состава**: Настройка количества игроков для каждого матча.

### ⚖️ Умная жеребьевка (Draft)
*   **Балансировка по рейтингу**: Алгоритм распределяет игроков так, чтобы силы команд были максимально равны.
*   **Учет позиций**: Бот следит, чтобы вратари и защитники не оказались все в одной команде.
*   **Несколько режимов**: Случайная жеребьевка или строго по статистике.

### 📊 Статистика и Профили
*   **Рейтинги игроков**: Личные характеристики (Атака, Защита, Скорость, ГК), которые влияют на жеребьевку.
*   **История матчей**: Сохранение результатов, авторов голов и ассистов.
*   **Таблица лидеров**: Наглядный рейтинг игроков в рамках сообщества.

---

## 🕹 Команды / Commands

| Command | Description (EN) | Описание (RU) | Access |
| :--- | :--- | :--- | :--- |
| `/poll` | Create match poll | Создать сбор на матч | Admin |
| `/admin` | Admin panel | Панель управления | Admin |
| `/set_player` | Find & edit player | Поиск и ред. игрока | Admin |
| `/table` | Show leaderboard | Таблица лидеров | All |
| `/help` | Help center | Справка | All |

---

## 📄 License
MIT. See [LICENSE](LICENSE) for details.
