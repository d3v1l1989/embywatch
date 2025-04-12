# JellyfinWatch 🎬

A Discord bot that monitors your Jellyfin server and displays real-time statistics in a beautiful dashboard. Built with Python and Discord.py.

## ✨ Features

- 📊 Real-time server statistics
- 📺 Library overview with item counts
- 👥 User activity monitoring
- 🎥 Currently playing content tracking
- ⚙️ Customizable dashboard appearance
- 🔄 Automatic updates every 30 seconds
- 🎨 Beautiful embed design with Jellyfin branding
- 🔒 Secure authentication with Jellyfin API
- 🛠️ Easy setup and configuration

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Jellyfin Server URL and API Key
- Discord Server with admin permissions

### Installation

1. Clone the repository:
```bash
git clone https://github.com/d3v1l1989/JellyfinWatch.git
cd JellyfinWatch
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your environment variables in `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token
JELLYFIN_URL=your_jellyfin_server_url
JELLYFIN_API_KEY=your_jellyfin_api_key
DISCORD_AUTHORIZED_USERS=user_id1,user_id2
```

4. Run the bot:
```bash
python main.py
```

## 🛠️ Configuration

The bot uses a `.env` file for configuration. Here are the available options:

- `DISCORD_TOKEN`: Your Discord bot token
- `JELLYFIN_URL`: Your Jellyfin server URL
- `JELLYFIN_API_KEY`: Your Jellyfin API key
- `DISCORD_AUTHORIZED_USERS`: Comma-separated list of Discord user IDs authorized to use admin commands

## 🤖 Commands

### Admin Commands
- `/setup` - Set up the dashboard in the current channel
- `/update_libraries` - Manually update library statistics
- `/toggle_episodes` - Toggle display of episode counts in library stats
- `/reload` - Reload the bot configuration
- `/help` - Show help information

## 🎨 Dashboard Features

The dashboard provides a comprehensive overview of your Jellyfin server:

- Server status and version
- System information (CPU, memory, disk usage)
- Library statistics with customizable display options
- Currently playing content
- Active user sessions
- Beautiful embed design with Jellyfin branding

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💖 Support

If this bot has helped you, consider supporting my work! Your support helps me maintain and improve this project.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/d3v1l1989)

## 🙏 Acknowledgments

- [Jellyfin](https://jellyfin.org/) for the amazing media server
- [Discord.py](https://discordpy.readthedocs.io/) for the Discord API wrapper
- All contributors and users of this bot
