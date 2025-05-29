# EmbyWatch 🎬

A Discord bot that monitors your Emby server and displays real-time statistics in a beautiful dashboard. Built with Python and Discord.py.

## ✨ Features

- 📊 Real-time server statistics
- 📺 Library overview with item counts and episode tracking
- 👥 User activity monitoring
- 🎥 Currently playing content tracking
- ⚙️ Customizable dashboard appearance
- 🔄 Automatic updates every 60 seconds
- 🎨 Beautiful embed design with Emby branding
- 🔒 Secure authentication with Emby API
- 🛠️ Easy setup and configuration
- 🎌 Smart emoji detection for different content types
- 🔄 Cog management system for modular functionality

## 📸 Screenshots

![Dashboard Preview](screenshots/dashboard.png)

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Emby Server URL, API Key, Username, Password
- Discord Server with admin permissions

### Creating a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" tab and click "Add Bot"
4. Under "Privileged Gateway Intents", enable:
   - PRESENCE INTENT
   - SERVER MEMBERS INTENT
   - MESSAGE CONTENT INTENT
5. Click "Reset Token" to get your bot token (save this for later)
6. Go to "OAuth2" → "URL Generator"
7. Select these scopes:
   - `bot`
   - `applications.commands`
8. Select these bot permissions:
   - `Send Messages`
   - `Embed Links`
   - `Attach Files`
   - `Read Message History`
   - `Use Slash Commands`
9. Copy the generated URL and open it in your browser to invite the bot to your server

### Installation

1. Clone the repository:
```bash
git clone https://github.com/d3v1l1989/embywatch.git
cd embywatch
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your environment variables in `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token
EMBY_URL=your_emby_server_url
EMBY_API_KEY=your_emby_api_key
EMBY_USERNAME=your_emby_username
EMBY_PASSWORD=your_emby_password
CHANNEL_ID=your_discord_channel_id
DISCORD_AUTHORIZED_USERS=user_id1,user_id2
RUNNING_IN_DOCKER=false
```

4. Run the bot:
```bash
python main.py
```

### Docker Installation

1. Create a `docker-compose.yml` file:
```yaml
version: '3.8'

services:
  embywatch:
    image: ghcr.io/d3v1l1989/embywatch:latest
    container_name: embywatch
    restart: unless-stopped
    user: "1000:1000"
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - EMBY_URL=${EMBY_URL}
      - EMBY_API_KEY=${EMBY_API_KEY}
      - EMBY_USERNAME=${EMBY_USERNAME}
      - EMBY_PASSWORD=${EMBY_PASSWORD}
      - CHANNEL_ID=${CHANNEL_ID}
      - DISCORD_AUTHORIZED_USERS=${DISCORD_AUTHORIZED_USERS}
      - RUNNING_IN_DOCKER=true
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

2. Create necessary directories and environment file:
```bash
# Create directories
mkdir -p data logs

# Set correct permissions
sudo chown -R 1000:1000 data logs

# Create and edit environment file

nano .env  # Edit with your configuration, use example above as template
```

3. Start the container:
```bash
docker compose up -d
```
4. Use /update_libraries command to update libraries after EmbyWatch starts


## 🛠️ Configuration

The bot uses a `.env` file for configuration. Here are the available options:

- `DISCORD_TOKEN`: Your Discord bot token
- `EMBY_URL`: Your Emby server URL
- `EMBY_API_KEY`: Your Emby API key
- `EMBY_USERNAME`: Your Emby username
- `EMBY_PASSWORD`: Your Emby password
- `CHANNEL_ID`: The Discord channel ID where the dashboard will be displayed
- `DISCORD_AUTHORIZED_USERS`: Comma-separated list of Discord user IDs authorized to use admin commands
- `RUNNING_IN_DOCKER`: Set to "true" if running in Docker, "false" otherwise

## 🤖 Commands

### Admin Commands
- `/update_libraries` - Update Emby library sections in the dashboard
- `/episodes` - Toggle display of Emby episode counts in library stats
- `/refresh` - Refresh the Emby dashboard embed immediately
- `/test_connection` - Test connection to the Emby server
- `/test-libraries` - Test Emby library statistics retrieval
- `/sync` - Sync Emby dashboard slash commands with Discord
- `/load` - Load a specific cog (admin only)
- `/unload` - Unload a specific cog (admin only)
- `/reload` - Reload a specific cog (admin only)
- `/cogs` - List all available cogs

## 🎨 Dashboard Features

The dashboard provides real-time information about your Emby server, including:
- Server status and uptime
- Active streams count
- Library statistics with smart emoji detection
- Episode counts for TV shows and anime libraries
- Beautiful Emby-themed design with official Emby green color scheme
