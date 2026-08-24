# 🌌 Galactic Manga Telegram Bot

A lightning-fast, feature-rich Telegram Bot built with `python-telegram-bot`, `Flask`, and `MongoDB` to manage manga channels, auto-buffer and broadcast new chapter releases, track user reading lists, manage bookmarks, provide inline search, and handle manga requests.

---

## ⚡ Key Features

- **🚀 High-Speed In-Memory Caching & RapidFuzz**: Sub-millisecond title search and indexed queries.
- **📦 Chapter Buffer & Auto-Broadcaster**: Groups batch PDF chapter uploads cleanly and posts updates with interactive read buttons.
- **📚 Bookmark & Reading List System**: Save bookmarks, track chapter progress, mark favorites, completed, on-hold, or dropped titles.
- **🔍 Inline & Group Search**: Search manga titles directly in groups or via Telegram inline mode (`@bot <title>`).
- **📊 Fast Statistics & Leaderboard**: Instant stats dashboard and top reader rankings powered by MongoDB aggregation pipelines.
- **📨 Manga Request Workflow**: Interactive request submission and admin approval/denial dashboard with direct user DM notifications.
- **🛡️ Admin & Broadcast Suite**: Broadcast messages across all managed channels and direct to user DMs with auto-logging and reliable deletion.
- **🌐 Cloud Keep-Alive**: Integrated Flask health-check server for 24/7 deployment on Render, Koyeb, Railway, or VPS.

---

## 🛠️ Tech Stack & Requirements

- **Python**: 3.10+ (Tested up to Python 3.13)
- **Database**: MongoDB (Atlas or self-hosted)
- **Core Libraries**:
  - `python-telegram-bot==13.15`
  - `pymongo==4.6.3`
  - `rapidfuzz==3.6.1`
  - `python-dotenv==1.0.1`
  - `Flask==3.0.3`
  - `pytz==2024.1`

---

## ⚙️ Configuration & Setup

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/galactic-update-bot.git
cd galactic-update-bot
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (refer to `.env.example`):
```env
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here
BOT_OWNER_ID=6600689593
UPDATE_CHANNEL_ID=-1002887680811
LOG_CHANNEL_ID=-1002182636182

# MongoDB Database Configuration
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
```

### 3. Run the Bot
```bash
python bot.py
```

---

## 📖 Command Reference

### 👤 User Commands
| Command | Description |
| :--- | :--- |
| `/start` | Launch interactive menu with anime quotes and quick buttons |
| `/help` | Display command guide and documentation |
| `/manga <title>` | Search for a manga in the database |
| `/profile` | View reading profile, badges, statistics, and rank |
| `/bookmark <title> <chapter>` | Save or update your current reading chapter |
| `/mybookmarks` | View and manage your saved bookmarks |
| `/clearbookmarks` | Clear all your bookmarks |
| `/recommend` | Get smart recommendations based on unread titles |
| `/leaderboard` | View top readers leaderboard |
| `/read`, `/fav`, `/completed`, `/hold`, `/drop` | View categorized lists |
| `/currentlyreading`, `/mylist` | Summary of ongoing and tracked titles |
| `/request <title>` | Submit a manga request to admins |

### 🛡️ Admin & Sudo Commands
| Command | Description |
| :--- | :--- |
| `/stats` | View instant database analytics, total users, and top manga |
| `/add <channel_id> <title>` | Register a manga channel and bind cover photo |
| `/addmanga <title> \| <link>` | Add a manga entry with image reply |
| `/editmanga <old> \| <new> \| <link>` | Edit manga title and channel link |
| `/removemanga <title>` | Remove a manga entry from the catalog |
| `/setchapters <title> <count>` | Set total chapter count for progress tracking |
| `/unpost <channel_id> <chapter>` | Unmark a chapter as posted |
| `/requestlist` | View and approve/deny pending user requests |
| `/broadcast <msg>` | Broadcast message to all tracked channels |
| `/delete_broadcast` | Delete broadcast message across all channels |
| `/dmbroadcast` | Broadcast message to all user DMs (rate-limited) |
| `/delete_dmbroadcast` | Delete broadcast message from all user DMs |
| `/addadmins <user_id>` | Grant admin/sudo privileges |
| `/removeadmins <user_id>` | Revoke admin/sudo privileges |
| `/sudo` | List all current admins and sudo users |
| `/refreshchannels` | Sync channel names from Telegram |
| `/checkchannels` | Audit bot administrator permissions across channels |

---

## 🐳 Docker Deployment

```bash
docker build -t galactic-bot .
docker run -d --name galactic-bot --env-file .env -p 10000:10000 galactic-bot
```

---

## 🔒 Security Best Practices
- Keep `.env` out of version control (protected by `.gitignore`).
- Never commit bot tokens or database passwords directly into code.
- Restrict MongoDB network access to trusted IPs or deployment clusters.
