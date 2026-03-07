# Virexa Project Execution Guide

This guide provides instructions on how to set up and run the Virexa Discord Bot and Dashboard.

## Prerequisites
- Python 3.10 or higher
- A Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- A Discord Client ID and Client Secret (for Dashboard OAuth2)

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Virexa
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root directory (or update the existing one) with the following content:
   ```env
   DISCORD_TOKEN="your_discord_bot_token"
   DATABASE_URL="sqlite+aiosqlite:///./virexa.db"
   DEFAULT_PREFIX="/"
   SECRET_KEY="your_random_secret_key"
   DISCORD_CLIENT_ID="your_discord_client_id"
   DISCORD_CLIENT_SECRET="your_discord_client_secret"
   DISCORD_REDIRECT_URI="http://localhost:8000/auth/callback"
   ```

## Running the Application

The project consists of two main components: the Discord Bot and the FastAPI Dashboard.

### 1. Run the Discord Bot
To start the bot, run:
```bash
python -m bot.main
```
The bot will initialize the database, sync slash commands, and log into Discord.

### 2. Run the Dashboard
To start the web dashboard, run:
```bash
uvicorn dashboard.main:app --host 0.0.0.0 --port 8000
```
The dashboard will be accessible at `http://localhost:8000`.

## Project Structure
- `bot/`: Discord bot logic (commands, events, moderation).
- `dashboard/`: FastAPI web application and routers.
- `database/`: Database models and connection logic.
- `templates/` & `static/`: Frontend files for the dashboard.
- `config/`: Configuration settings and environment loading.

## Notes
- The application uses SQLite by default (`virexa.db`).
- Ensure the `DISCORD_REDIRECT_URI` matches the one configured in your Discord Developer Portal under OAuth2.




# Easy WAY
Just run the 

```bash
# Run the Bot
python -m bot.main
# Run the Dashboard
uvicorn dashboard.main:app --host 0.0.0.0 --port 8000
```