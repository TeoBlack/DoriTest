# 📚 Dori Bot – English Vocabulary Learning Assistant

**Dori** is a Telegram bot built for students and teachers to support English vocabulary learning. It helps students practice, track, and grow their personal word banks — while enabling teachers to manage and expand the main word database used across the group.

---

## 🚀 Features

### 🧑‍🎓 For Students
- Personal vocabulary dictionary
- Flashcard mode (word recall)
- Self-check mode (multiple-choice)
- Progress tracking (score, levels, attempts)
- Achievements and gamification

### 👩‍🏫 For Teachers
- Add and edit global vocabulary words
- See student progress summaries
- Upload vocabulary to central DB

---

## 🛠️ Tech Stack

- **Python 3.11+**
- [aiogram](https://github.com/aiogram/aiogram) – async Telegram bot framework
- **SQLite3** – for user data and vocabulary
- **Pillow** – for flashcard visuals
- **python-dotenv** – for secure environment config

---

## 🔒 Environment Setup

Create a `.env` file with your Telegram bot token:

```env
BOT_TOKEN= ACTUAL BOT TOKEN HERE
