import discord
from discord.ext import commands, tasks
import requests
import time
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from discord import app_commands
from main import is_authorized

RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"

if not RUNNING_IN_DOCKER:
    load_dotenv()

class JellyfinCore(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("jellywatch_bot.jellyfin")

        # Load environment variables
        self.JELLYFIN_URL = os.getenv("JELLYFIN_URL")
        self.JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
        self.JELLYFIN_USERNAME = os.getenv("JELLYFIN_USERNAME")
        self.JELLYFIN_PASSWORD = os.getenv("JELLYFIN_PASSWORD")
        channel_id = os.getenv("CHANNEL_ID")
        if channel_id is None:
            self.logger.error("CHANNEL_ID not set in .env file")
            raise ValueError("CHANNEL_ID must be set in .env")
        self.CHANNEL_ID = int(channel_id)

        # File paths
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.MESSAGE_ID_FILE = os.path.join(self.current_dir, "..", "data", "dashboard_message_id.json")
        self.USER_MAPPING_FILE = os.path.join(self.current_dir, "..", "data", "user_mapping.json")
        self.CONFIG_FILE = os.path.join(self.current_dir, "..", "data", "config.json")

        # Initialize state
        self.config = self._load_config()
        self.jellyfin_start_time: Optional[float] = None
        self.dashboard_message_id = self._load_message_id()
        self.last_scan = datetime.now()
        self.offline_since: Optional[datetime] = None
        self.stream_debug = False

        # Cache settings
        self.library_cache: Dict[str, Dict[str, Any]] = {}
        self.last_library_update: Optional[datetime] = None
        self.library_update_interval = self.config.get("cache", {}).get("library_update_interval", 900)

        self.user_mapping = self._load_user_mapping()
        self.update_status.start()
        self.update_dashboard.start()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.json with defaults if unavailable."""
        default_config = {
            "dashboard": {"name": "Jellyfin Dashboard", "icon_url": "", "footer_icon_url": ""},
            "jellyfin_sections": {"show_all": True, "sections": {}},
            "presence": {
                "sections": [],
                "offline_text": "🔴 Server Offline!",
                "stream_text": "{count} active Stream{s} 🟢",
            },
            "cache": {"library_update_interval": 900},
        }
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return {**default_config, **config}  # Merge with defaults
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load config: {e}. Using defaults.")
            return default_config

    def _load_message_id(self) -> Optional[int]:
        """Load the dashboard message ID from file."""
        if not os.path.exists(self.MESSAGE_ID_FILE):
            return None
        try:
            with open(self.MESSAGE_ID_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("message_id"))
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Failed to load message ID: {e}")
            return None

    def _save_message_id(self, message_id: int) -> None:
        """Save the dashboard message ID to file."""
        try:
            with open(self.MESSAGE_ID_FILE, "w", encoding="utf-8") as f:
                json.dump({"message_id": message_id}, f)
        except OSError as e:
            self.logger.error(f"Failed to save message ID: {e}")

    def _load_user_mapping(self) -> Dict[str, str]:
        """Load user mapping from JSON file."""
        try:
            with open(self.USER_MAPPING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load user mapping: {e}")
            return {}

    def connect_to_jellyfin(self) -> bool:
        """Attempt to establish a connection to the Jellyfin server."""
        try:
            # Common headers for all requests
            headers = {
                "X-Emby-Client": "JellyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "JellyWatch",
                "X-Emby-Device-Id": "jellywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"JellyWatch\", Device=\"JellyWatch\", DeviceId=\"jellywatch-bot\", Version=\"1.0.0\""
            }

            # First try with API key if available
            if self.JELLYFIN_API_KEY:
                headers["X-Emby-Token"] = self.JELLYFIN_API_KEY
                response = requests.get(f"{self.JELLYFIN_URL}/System/Info", headers=headers)
                if response.status_code == 200:
                    if self.jellyfin_start_time is None:
                        self.jellyfin_start_time = time.time()
                    return True
                elif response.status_code == 401:
                    self.logger.error("Invalid API key provided")
                    return False
                else:
                    self.logger.error(f"Failed to connect with API key: HTTP {response.status_code}")
                    return False

            # If API key fails or not available, try username/password
            if self.JELLYFIN_USERNAME and self.JELLYFIN_PASSWORD:
                auth_data = {
                    "Username": self.JELLYFIN_USERNAME,
                    "Pw": self.JELLYFIN_PASSWORD
                }
                response = requests.post(
                    f"{self.JELLYFIN_URL}/Users/AuthenticateByName",
                    json=auth_data,
                    headers=headers
                )
                if response.status_code == 200:
                    if self.jellyfin_start_time is None:
                        self.jellyfin_start_time = time.time()
                    return True
                elif response.status_code == 401:
                    self.logger.error("Invalid username or password")
                    return False
                else:
                    self.logger.error(f"Failed to authenticate with username/password: HTTP {response.status_code}")
                    return False

            self.logger.error("No authentication method provided (API key or username/password required)")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Jellyfin server: {e}")
            self.jellyfin_start_time = None
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """Retrieve current Jellyfin server status and statistics."""
        if not self.connect_to_jellyfin():
            return self.get_offline_info()
        try:
            self.offline_since = None
            return {
                "status": "🟢 Online",
                "uptime": self.calculate_uptime(),
                "library_stats": self.get_library_stats(),
                "active_users": self.get_active_streams(),
                "current_streams": self.get_sessions(),
            }
        except Exception as e:
            self.logger.error(f"Error retrieving server info: {e}")
            return self.get_offline_info()

    def calculate_uptime(self) -> str:
        """Calculate Jellyfin server uptime as a formatted string."""
        if not self.jellyfin_start_time:
            return "Offline"
        total_minutes = int((time.time() - self.jellyfin_start_time) / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return "99+ Hours" if hours > 99 else f"{hours:02d}:{minutes:02d}"

    def get_library_stats(self) -> Dict[str, Dict[str, Any]]:
        """Fetch and cache Jellyfin library statistics."""
        current_time = datetime.now()
        if (
            self.last_library_update
            and (current_time - self.last_library_update).total_seconds() <= self.library_update_interval
        ):
            return self.library_cache

        if not self.connect_to_jellyfin():
            return self.library_cache

        try:
            headers = {
                "X-Emby-Token": self.JELLYFIN_API_KEY,
                "X-Emby-Client": "JellyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "JellyWatch",
                "X-Emby-Device-Id": "jellywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"JellyWatch\", Device=\"JellyWatch\", DeviceId=\"jellywatch-bot\", Version=\"1.0.0\""
            }
            
            response = requests.get(f"{self.JELLYFIN_URL}/Library/VirtualFolders", headers=headers)
            if response.status_code != 200:
                self.logger.error(f"Failed to get library folders: HTTP {response.status_code}")
                return self.library_cache

            libraries = response.json()
            stats: Dict[str, Dict[str, Any]] = {}
            jellyfin_config = self.config["jellyfin_sections"]
            configured_sections = jellyfin_config["sections"]

            for library in libraries:
                name = library["Name"]
                if not jellyfin_config["show_all"] and name not in configured_sections:
                    continue

                config = configured_sections.get(name, {
                    "display_name": name,
                    "emoji": "🎬",
                    "show_episodes": False
                })

                # Get item counts
                params = {
                    "ParentId": library["ItemId"],
                    "Recursive": True,
                    "IncludeItemTypes": "Movie,Series,Episode"
                }
                items_response = requests.get(
                    f"{self.JELLYFIN_URL}/Items",
                    headers=headers,
                    params=params
                )
                
                if items_response.status_code == 200:
                    items = items_response.json()
                    movie_count = sum(1 for item in items["Items"] if item["Type"] == "Movie")
                    series_count = sum(1 for item in items["Items"] if item["Type"] == "Series")
                    episode_count = sum(1 for item in items["Items"] if item["Type"] == "Episode")

                    stats[name] = {
                        "count": movie_count + series_count,
                        "episodes": episode_count if config["show_episodes"] else 0,
                        "display_name": config["display_name"],
                        "emoji": config["emoji"],
                        "show_episodes": config["show_episodes"],
                    }
                else:
                    self.logger.error(f"Failed to get items for library {name}: HTTP {items_response.status_code}")

            self.library_cache = stats
            self.last_library_update = current_time
            self.logger.info(f"Library stats updated and cached (interval: {self.library_update_interval}s)")
            return stats
        except Exception as e:
            self.logger.error(f"Error updating library stats: {e}")
            return self.library_cache

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Get current Jellyfin sessions."""
        if not self.connect_to_jellyfin():
            return []

        try:
            headers = {
                "X-Emby-Token": self.JELLYFIN_API_KEY,
                "X-Emby-Client": "JellyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "JellyWatch",
                "X-Emby-Device-Id": "jellywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"JellyWatch\", Device=\"JellyWatch\", DeviceId=\"jellywatch-bot\", Version=\"1.0.0\""
            }
            
            response = requests.get(f"{self.JELLYFIN_URL}/Sessions", headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.logger.error("Invalid API key when fetching sessions")
                return []
            else:
                self.logger.error(f"Failed to get sessions: HTTP {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"Error getting sessions: {e}")
            return []

    def get_active_streams(self) -> List[str]:
        """Retrieve formatted information about active Jellyfin streams."""
        sessions = self.get_sessions()
        if self.stream_debug:
            self.logger.debug(f"Found {len(sessions)} active sessions")
        
        active_streams = []
        for idx, session in enumerate(sessions, start=1):
            if session.get("NowPlayingItem"):
                stream_info = self.format_stream_info(session, idx)
                if stream_info:
                    active_streams.append(stream_info)
                    if self.stream_debug:
                        self.logger.debug(f"Formatted Stream Info:\n{stream_info}\n{'='*50}")
        
        return active_streams

    def format_stream_info(self, session: Dict[str, Any], idx: int) -> str:
        """Format Jellyfin session information into a readable string."""
        try:
            item = session["NowPlayingItem"]
            user = session.get("UserName", "Unknown")
            player = session.get("Client", "Unknown")
            
            # Get progress percentage
            position_ticks = session.get("PlayState", {}).get("PositionTicks", 0)
            runtime_ticks = item.get("RunTimeTicks", 0)
            progress = (position_ticks / runtime_ticks * 100) if runtime_ticks else 0
            
            # Format title
            title = self._get_formatted_title(item)
            
            # Get quality info
            quality = "Unknown"
            if "MediaStreams" in item:
                for stream in item["MediaStreams"]:
                    if stream.get("Type") == "Video":
                        quality = f"{stream.get('Width', '?')}x{stream.get('Height', '?')}"
                        break
            
            # Format stream info
            stream_info = (
                f"**{idx}. {title}**\n"
                f"📱 {player}\n"
                f"📊 {progress:.1f}% | {quality}"
            )
            
            return stream_info
        except Exception as e:
            self.logger.error(f"Error formatting stream info: {e}")
            return ""

    def _get_formatted_title(self, item: Dict[str, Any]) -> str:
        """Format the title of a Jellyfin item."""
        try:
            if item["Type"] == "Episode":
                series_name = item.get("SeriesName", "Unknown Series")
                season_episode = f"S{item.get('ParentIndexNumber', 0):02d}E{item.get('IndexNumber', 0):02d}"
                episode_name = item.get("Name", "Unknown Episode")
                return f"{series_name} - {season_episode} - {episode_name}"
            else:
                return item.get("Name", "Unknown")
        except Exception as e:
            self.logger.error(f"Error formatting title: {e}")
            return "Unknown"

    def get_offline_info(self) -> Dict[str, Any]:
        """Return offline status information."""
        if self.offline_since is None:
            self.offline_since = datetime.now()
        
        offline_duration = datetime.now() - self.offline_since
        hours = int(offline_duration.total_seconds() / 3600)
        minutes = int((offline_duration.total_seconds() % 3600) / 60)
        
        return {
            "status": "🔴 Offline",
            "uptime": f"Offline for {hours:02d}:{minutes:02d}",
            "library_stats": self.library_cache,
            "active_users": [],
            "current_streams": [],
        }

    @tasks.loop(minutes=5)
    async def update_status(self) -> None:
        """Update the bot's status with Jellyfin information."""
        try:
            info = self.get_server_info()
            if info["status"] == "🟢 Online":
                streams = len(info["current_streams"])
                presence_text = self.config["presence"]["stream_text"].format(
                    count=streams,
                    s="s" if streams != 1 else ""
                )
            else:
                presence_text = self.config["presence"]["offline_text"]
            
            await self.bot.change_presence(activity=discord.Game(name=presence_text))
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")

    @tasks.loop(minutes=1)
    async def update_dashboard(self) -> None:
        """Update the Discord dashboard with current Jellyfin information."""
        try:
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if not channel:
                self.logger.error(f"Channel {self.CHANNEL_ID} not found")
                return

            info = self.get_server_info()
            embed = await self.create_dashboard_embed(info)
            await self._update_dashboard_message(channel, embed)
        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}")

    async def create_dashboard_embed(self, info: Dict[str, Any]) -> discord.Embed:
        """Create the dashboard embed with server information."""
        embed = discord.Embed(
            title="Jellyfin Server Dashboard",
            description="Real-time server status and statistics",
            color=discord.Color.blue()
        )
        
        # Set thumbnail to Jellyfin logo
        embed.set_thumbnail(url="https://raw.githubusercontent.com/jellyfin/jellyfin-ux/master/branding/SVG/icon-transparent.svg")
        
        # Add fields
        await self._add_embed_fields(embed, info)
        
        # Set footer with JellyfinWatch branding
        embed.set_footer(
            text="Powered by JellyfinWatch",
            icon_url="https://raw.githubusercontent.com/jellyfin/jellyfin-ux/master/branding/SVG/icon-transparent.svg"
        )
        
        return embed

    async def _add_embed_fields(self, embed: discord.Embed, info: Dict[str, Any]) -> None:
        """Add fields to the dashboard embed."""
        # Server Status
        embed.add_field(
            name="Server Status",
            value=f"{info['status']}\nUptime: {info['uptime']}",
            inline=False
        )

        # Library Statistics - One field per library
        for section, stats in info["library_stats"].items():
            # Get the color from config or use default
            color = self.config["jellyfin_sections"]["sections"].get(section, {}).get("color", "#00A4DC")
            # Convert hex color to discord.Color
            color = discord.Color.from_str(color)
            
            # Create a rich field for each library
            stat_text = f"{stats['emoji']} **{stats['display_name']}**\n"
            
            # Add items count with code block for darker background
            stat_text += f"```css\nTotal Items: {stats['count']}\n```\n"
            
            if stats["show_episodes"] and stats["episodes"] > 0:
                stat_text += f"```css\nEpisodes: {stats['episodes']}\n```\n"
            if stats.get("size", 0) > 0:
                stat_text += f"```css\nSize: {stats['size']}\n```\n"
            
            embed.add_field(
                name="\u200b",  # Empty name for spacing
                value=stat_text,
                inline=True
            )

        # Active Streams
        if info["active_users"]:
            streams_text = "**Active Streams**\n"
            for stream in info["active_users"]:
                streams_text += f"```css\n{stream}\n```\n"
            embed.add_field(
                name="\u200b",  # Empty name for spacing
                value=streams_text,
                inline=False
            )
        else:
            embed.add_field(
                name="\u200b",  # Empty name for spacing
                value="**Active Streams**\n```css\nNo active streams\n```",
                inline=False
            )

    async def _update_dashboard_message(self, channel: discord.TextChannel, embed: discord.Embed) -> None:
        """Update or create the dashboard message."""
        try:
            if self.dashboard_message_id:
                try:
                    message = await channel.fetch_message(self.dashboard_message_id)
                    await message.edit(embed=embed)
                    return
                except discord.NotFound:
                    self.dashboard_message_id = None
                except discord.Forbidden:
                    self.logger.error("Bot doesn't have permission to edit messages in the channel")
                    return

            message = await channel.send(embed=embed)
            self.dashboard_message_id = message.id
            self._save_message_id(message.id)
        except Exception as e:
            self.logger.error(f"Error updating dashboard message: {e}")

    @app_commands.command(name="update_libraries", description="Update config.json with current Jellyfin libraries")
    @app_commands.check(is_authorized)
    async def update_libraries(self, interaction: discord.Interaction) -> None:
        """Update the config.json file with current Jellyfin libraries."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not self.connect_to_jellyfin():
                await interaction.followup.send("❌ Failed to connect to Jellyfin server.")
                return

            headers = {
                "X-Emby-Token": self.JELLYFIN_API_KEY,
                "X-Emby-Client": "JellyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "JellyWatch",
                "X-Emby-Device-Id": "jellywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"JellyWatch\", Device=\"JellyWatch\", DeviceId=\"jellywatch-bot\", Version=\"1.0.0\""
            }
            
            response = requests.get(f"{self.JELLYFIN_URL}/Library/VirtualFolders", headers=headers)
            if response.status_code != 200:
                await interaction.followup.send(f"❌ Failed to get library folders: HTTP {response.status_code}")
                return

            libraries = response.json()
            current_config = self._load_config()
            
            # Default emojis for different library types
            default_emojis = {
                "movie": "🎥",
                "tvshow": "📺",
                "music": "🎵",
                "documentary": "📚",
                "anime": "🎌",
                "default": "🎬"
            }

            # Update sections in config
            sections = {}
            for library in libraries:
                name = library["Name"]
                # Try to determine library type from name
                library_type = "default"
                if any(keyword in name.lower() for keyword in ["movie", "film"]):
                    library_type = "movie"
                elif any(keyword in name.lower() for keyword in ["tv", "show", "series"]):
                    library_type = "tvshow"
                elif any(keyword in name.lower() for keyword in ["music", "song"]):
                    library_type = "music"
                elif any(keyword in name.lower() for keyword in ["documentary", "doc"]):
                    library_type = "documentary"
                elif any(keyword in name.lower() for keyword in ["anime", "cartoon"]):
                    library_type = "anime"

                # Use existing config if available, otherwise create new
                existing_config = current_config["jellyfin_sections"]["sections"].get(name, {})
                sections[name] = {
                    "display_name": existing_config.get("display_name", name),
                    "emoji": existing_config.get("emoji", default_emojis[library_type]),
                    "show_episodes": existing_config.get("show_episodes", library_type in ["tvshow", "anime"]),
                    "color": existing_config.get("color", "#00A4DC")  # Default Jellyfin blue
                }

            # Update config
            current_config["jellyfin_sections"]["sections"] = sections
            current_config["jellyfin_sections"]["show_all"] = False

            # Save updated config
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(current_config, f, indent=4)

            # Reload config
            self.config = self._load_config()

            await interaction.followup.send("✅ Successfully updated library configuration!")
        except Exception as e:
            self.logger.error(f"Error updating libraries: {e}")
            await interaction.followup.send(f"❌ Error updating libraries: {e}")

async def setup(bot: commands.Bot) -> None:
    """Add the JellyfinCore cog to the bot."""
    await bot.add_cog(JellyfinCore(bot)) 