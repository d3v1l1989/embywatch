# JellyWatch - Your Jellyfin Dashboard in Discord

![License](https://img.shields.io/badge/license-MIT-blue.svg)
[![Version](https://img.shields.io/github/release/d3v1l1989/JellyfinWatch.svg?style=flat-square)](https://github.com/d3v1l1989/JellyfinWatch/releases/latest)
![Python](https://img.shields.io/badge/python-3.8+-yellow.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blueviolet.svg)
![Jellyfin](https://img.shields.io/badge/jellyfin-compatible-orange.svg)

JellyWatch is a Discord bot that brings your Jellyfin media server to life with a real-time dashboard. Monitor active streams, track SABnzbd downloads, and check server uptime—all directly in your Discord server. Designed for Jellyfin enthusiasts, JellyWatch delivers a sleek, embed-based interface to keep you informed about your media ecosystem.

## Features

- **Jellyfin Monitoring**: Displays active streams with details like title, user, progress, quality, and player info.
- **SABnzbd Integration**: Tracks ongoing downloads with progress, speed, and size.
- **Uptime Tracking**: Shows server uptime over 24h, 7d, and 30d with percentage and duration.
- **Customizable Dashboard**: Updates every minute with a clean Discord embed, fully configurable via JSON.
- **Bot Presence**: Reflects Jellyfin status and stream count in the bot's Discord status.
- **Logging**: Detailed logs for debugging and tracking bot activity.
- **Library Management**: 
  - Automatic library detection and configuration
  - Customizable library display names and emojis
  - Toggle episode count visibility per library
  - Hide empty libraries from the dashboard
- **Modern UI**: 
  - Clean, organized dashboard layout
  - Jellyfin-branded thumbnails and icons
  - Code block formatting for better readability
  - Dark mode compatible

## Project Structure

```
📦 JellyWatch
├─ /cogs                # Bot extensions (cogs) for modular functionality
│  ├─ jellyfin_core.py  # Core Jellyfin monitoring and dashboard logic
│  ├─ sabnzbd.py        # SABnzbd download tracking
│  └─ uptime.py         # Server uptime monitoring
├─ /data               # Configuration and state files
│  ├─ config.json      # Bot settings (e.g., dashboard config, Jellyfin sections)
│  ├─ dashboard_message_id.json  # Stores the ID of the dashboard message
│  └─ user_mapping.json  # Maps Jellyfin usernames to display names
├─ /logs               # Log files for debugging
│  └─ jellywatch_debug.log  # Rotated debug logs (updated daily, 7-day backup)
├─ .env                # Environment variables (private, not tracked)
├─ .env.example        # Template for .env configuration
├─ .gitignore          # Git ignore rules (e.g., logs, .env)
├─ main.py             # Entry point for the bot
├─ README.md           # This file
└─ requirements.txt    # Python dependencies
```

## Setup

### Prerequisites
- Python 3.8+
- A Jellyfin Media Server with API access
- SABnzbd (optional, for download tracking)
- Uptime Kuma (optional, for uptime monitoring)
- A Discord bot token

### Installation local
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/d3v1l1989/JellyfinWatch.git
   cd JellyfinWatch
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with your details (see below).

4. **Run the Bot**:
   ```bash
   python main.py
   ```
   
### Installation docker
1. **Install the container and edit the required environment variables:**
	- See the full list of available envs further below. 
	- Make sure to mount the volumes for persistent config changes and logs.
```yaml
version: '3.8'

services:
  jellywatch:
    image: ghcr.io/d3v1l1989/jellyfinwatch:latest
    container_name: jellywatch
    restart: unless-stopped
    user: "1000:1000"
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - JELLYFIN_URL=${JELLYFIN_URL}
      - JELLYFIN_API_KEY=${JELLYFIN_API_KEY}
      - JELLYFIN_USERNAME=${JELLYFIN_USERNAME}
      - JELLYFIN_PASSWORD=${JELLYFIN_PASSWORD}
      - CHANNEL_ID=${CHANNEL_ID}
      - DISCORD_AUTHORIZED_USERS=${DISCORD_AUTHORIZED_USERS}
      - RUNNING_IN_DOCKER=true
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```   

2. **Create necessary directories and environment file:**
   ```bash
   # Create directories
   mkdir -p data logs
   
   # Set correct permissions (assuming UID 1000)
   sudo chown -R 1000:1000 data logs
   
   # Copy and edit environment file
   cp .env.example .env
   nano .env  # Edit with your configuration
   ```

3. **Login to GitHub Container Registry:**
   ```bash
   docker login ghcr.io -u YOUR_GITHUB_USERNAME
   ```
   (Use a GitHub Personal Access Token as your password)

4. **Start the container:**
   ```bash
   docker compose up -d
   ```

### Environment Variables (`.env`)
The `.env` file stores sensitive configuration. Use the following format:

```
DISCORD_TOKEN=your_discord_bot_token
DISCORD_AUTHORIZED_USERS=123456789012345678,987654321098765432  # Comma-separated user IDs
JELLYFIN_URL=https://your-jellyfin-server:8096
JELLYFIN_API_KEY=your_jellyfin_api_key
# Alternative authentication (use either API key or username/password)
JELLYFIN_USERNAME=your_jellyfin_username
JELLYFIN_PASSWORD=your_jellyfin_password
CHANNEL_ID=your_discord_channel_id
SABNZBD_URL=http://your-sabnzbd-server:8080
SABNZBD_API_KEY=your_sabnzbd_api_key
UPTIME_URL=https://your-uptime-kuma-server:3001
UPTIME_USERNAME=your_uptime_kuma_username
UPTIME_PASSWORD=your_uptime_kuma_password
UPTIME_MONITOR_ID=your_monitor_id
```

- `DISCORD_TOKEN`: Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `DISCORD_AUTHORIZED_USERS`: List of user IDs allowed to manage cogs (e.g., `!load`, `!unload`).
- `JELLYFIN_URL`: URL to your Jellyfin server (include protocol and port).
- `JELLYFIN_API_KEY`: Your Jellyfin API key (get from Jellyfin dashboard).
- `JELLYFIN_USERNAME` & `JELLYFIN_PASSWORD`: Alternative authentication method.
- `CHANNEL_ID`: Discord channel ID where the dashboard embed appears.
- `SABNZBD_URL` & `SABNZBD_API_KEY`: Optional, for SABnzbd integration (get API key from SABnzbd settings).
- `UPTIME_URL`: Optional, URL to your Uptime Kuma server (e.g., https://uptime.example.com:3001)
- `UPTIME_USERNAME`: Optional, Username for your Uptime Kuma instance
- `UPTIME_PASSWORD`: Optional, Password for your Uptime Kuma instance
- `UPTIME_MONITOR_ID`: Optional, The specific monitor ID from Uptime Kuma to track server uptime

## Configuration

JellyWatch is customized via `/data/config.json`. Below is the structure with example values based on your setup:

```json
{
    "dashboard": {
        "name": "Your Jellyfin Dashboard",
        "icon_url": "https://example.com/icon.png",
        "footer_icon_url": "https://example.com/icon.png"
    },
    "jellyfin_sections": {
        "show_all": false,
        "sections": {
            "Movies": {
                "display_name": "Movies",
                "emoji": "🎥",
                "show_episodes": false
            },
            "Shows": {
                "display_name": "Shows",
                "emoji": "📺",
                "show_episodes": true
            },
            "Documentaries": {
                "display_name": "Documentaries",
                "emoji": "📚",
                "show_episodes": false
            }
        }
    },
    "presence": {
        "sections": [
            {
                "section_title": "Movies",
                "display_name": "Movies",
                "emoji": "🎥"
            }
        ],
        "offline_text": "🔴 Server Offline!",
        "stream_text": "{count} active Stream{s} 🟢"
    },
    "cache": {
        "library_update_interval": 900
    }
}
```

## Commands

JellyWatch provides several slash commands for managing your dashboard:

- `/update_libraries`: Update library sections in the dashboard
- `/episodes`: Toggle episode numbers display in the dashboard
- `/refresh`: Refresh the dashboard embed immediately
- `/sync`: Sync slash commands with Discord

## Library Management

### Automatic Library Detection
JellyWatch automatically detects your Jellyfin libraries and assigns appropriate emojis based on their names. You can customize these settings through the dashboard configuration.

### Customizing Libraries
Each library can be configured with:
- Custom display name
- Custom emoji
- Episode count visibility toggle

### Episode Count Control
You can toggle episode count visibility for all libraries at once using the `/episodes` command. This setting is persisted across bot restarts.

### Empty Libraries
Libraries with no items are automatically hidden from the dashboard to keep it clean and focused on active content.

## Dashboard Features

### Real-time Updates
- Server status (online/offline)
- Active stream count and details
- Library statistics
- Uptime information

### Modern UI Elements
- Jellyfin-branded thumbnails and icons
- Code block formatting for better readability
- Dark mode compatible design
- Clean, organized layout

### Customization Options
- Custom server name
- Custom dashboard title
- Custom emojis for libraries
- Toggleable episode counts
- Configurable update intervals

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Star History

<a href="https://www.star-history.com/#d3v1l1989/JellyfinWatch&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=d3v1l1989/JellyfinWatch&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=d3v1l1989/JellyfinWatch&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=d3v1l1989/JellyfinWatch&type=Date" />
 </picture>
</a>
