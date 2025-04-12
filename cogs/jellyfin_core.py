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
import asyncio

# Library name to emoji mapping
LIBRARY_EMOJIS = {
    "movies": "🎬",
    "movie": "🎬",
    "films": "🎬",
    "tv": "📺",
    "television": "📺",
    "shows": "📺",
    "series": "📺",
    "music": "🎵",
    "songs": "🎵",
    "books": "📚",
    "audiobooks": "📚",
    "photos": "📸",
    "pictures": "📸",
    "images": "📸",
    "home videos": "🎥",
    "videos": "🎥",
    "anime": "🎎",
    "cartoons": "🎎",
    "documentaries": "📽️",
    "docs": "📽️",
    "kids": "👶",
    "children": "👶",
    "family": "👶",
    "default": "📁"  # Default emoji for unmatched libraries
}

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

    def _format_size(self, size_bytes: int) -> str:
        """Convert bytes to a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

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

    @tasks.loop(seconds=30)
    async def update_status(self) -> None:
        """Update bot's status with current stream count."""
        try:
            sessions = self.get_sessions()
            current_streams = len(sessions) if sessions else 0
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{current_streams} stream{'s' if current_streams != 1 else ''}"
            )
            await self.bot.change_presence(activity=activity)
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")

    @tasks.loop(seconds=60)
    async def update_dashboard(self) -> None:
        """Update the dashboard message periodically."""
        try:
            info = await self.get_server_info()
            if not info:
                return

            channel = self.bot.get_channel(self.CHANNEL_ID)
            if not channel:
                self.logger.error("Dashboard channel not found")
                return

            embed = await self.create_dashboard_embed(info)
            await self._update_dashboard_message(channel, embed)
        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}")

    async def get_server_info(self) -> Dict[str, Any]:
        """Get server information from Jellyfin."""
        try:
            if not self.connect_to_jellyfin():
                return {}

            headers = {
                "X-Emby-Token": self.JELLYFIN_API_KEY,
                "X-Emby-Client": "JellyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "JellyWatch",
                "X-Emby-Device-Id": "jellywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"JellyWatch\", Device=\"JellyWatch\", DeviceId=\"jellywatch-bot\", Version=\"1.0.0\""
            }

            # Get system info
            response = requests.get(f"{self.JELLYFIN_URL}/System/Info", headers=headers)
            if response.status_code != 200:
                return {}

            system_info = response.json()
            
            # Get sessions
            sessions = self.get_sessions()
            current_streams = len([s for s in sessions if s.get("NowPlayingItem")]) if sessions else 0

            # Get library stats
            library_stats = self.get_library_stats()
            total_items = sum(int(stats.get("count", 0)) for stats in library_stats.values())
            total_episodes = sum(int(episodes) for stats in library_stats.values() 
                               if (episodes := stats.get("episodes")) is not None)

            return {
                "server_name": system_info.get("ServerName", "Unknown Server"),
                "version": system_info.get("Version", "Unknown Version"),
                "operating_system": system_info.get("OperatingSystem", "Unknown OS"),
                "current_streams": current_streams,
                "total_items": total_items,
                "total_episodes": total_episodes,
                "library_stats": library_stats
            }
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return {}

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
            
            # Get all libraries
            response = requests.get(f"{self.JELLYFIN_URL}/Library/VirtualFolders", headers=headers)
            if response.status_code != 200:
                self.logger.error(f"Failed to get library folders: HTTP {response.status_code}")
                return self.library_cache

            libraries = response.json()
            stats: Dict[str, Dict[str, Any]] = {}
            jellyfin_config = self.config["jellyfin_sections"]
            configured_sections = jellyfin_config["sections"]

            for library in libraries:
                library_id = library.get("ItemId")
                library_name = library.get("Name", "").lower()
                
                if not jellyfin_config["show_all"] and library_id not in configured_sections:
                    continue

                # Get library configuration
                config = configured_sections.get(library_id, {
                    "display_name": library.get("Name", "Unknown Library"),
                    "emoji": LIBRARY_EMOJIS["default"],
                    "show_episodes": False
                })

                # Find matching emoji based on library name
                emoji = LIBRARY_EMOJIS["default"]
                for key, value in LIBRARY_EMOJIS.items():
                    if key in library_name:
                        emoji = value
                        break

                # Get item counts
                params = {
                    "ParentId": library_id,
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

                    # Create base stats dictionary
                    library_stats = {
                        "count": movie_count + series_count,
                        "display_name": config.get("display_name", library.get("Name", "Unknown Library")),
                        "emoji": emoji
                    }

                    # Only add episodes if show_episodes is True
                    if config.get("show_episodes", False):
                        library_stats["episodes"] = episode_count

                    stats[library_id] = library_stats
                else:
                    self.logger.error(f"Failed to get items for library {library_name}: HTTP {items_response.status_code}")

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

    async def create_dashboard_embed(self, info: Dict[str, Any]) -> discord.Embed:
        """Create the dashboard embed with server information."""
        embed = discord.Embed(
            title=f"📺 {info.get('server_name', 'Jellyfin Server')}",
            description="Real-time server status and statistics",
            color=discord.Color.blue()
        )
        
        # Set thumbnail to Jellyfin logo (512x512 version)
        embed.set_thumbnail(url="https://static-00.iconduck.com/assets.00/jellyfin-icon-512x512-jcuy5qbi.png")
        
        # Add server status
        status = "🟢 Online" if info else "🔴 Offline"
        uptime = self.calculate_uptime()
        embed.add_field(
            name="Server Status",
            value=f"{status}\nUptime: {uptime}",
            inline=False
        )
        
        # Add active streams
        current_streams = info.get('current_streams', 0)
        embed.add_field(
            name="Active Streams",
            value=f"```css\n{current_streams} active stream{'s' if current_streams != 1 else ''}\n```",
            inline=False
        )
        
        # Add library statistics
        library_stats = info.get('library_stats', {})
        if library_stats:
            stats_text = ""
            for library_id, stats in library_stats.items():
                if stats.get('count', 0) > 0:  # Only show libraries with items
                    stats_text += f"{stats.get('emoji', '📁')} **{stats.get('display_name', 'Unknown Library')}**\n"
                    stats_text += f"```css\nTotal Items: {stats.get('count', 0)}\n```\n"
                    # Only show episodes if the key exists in the stats
                    if 'episodes' in stats:
                        stats_text += f"```css\nEpisodes: {stats['episodes']}\n```\n"
            if stats_text:  # Only add the field if there are libraries to show
                embed.add_field(
                    name="Library Statistics",
                    value=stats_text,
                    inline=False
                )
        
        # Set footer with JellyfinWatch branding
        embed.set_footer(
            text="Powered by JellyfinWatch",
            icon_url="https://static-00.iconduck.com/assets.00/jellyfin-icon-96x96-h2vkd1yr.png"
        )
        
        return embed

    async def _update_dashboard_message(self, channel: discord.TextChannel, embed: discord.Embed) -> None:
        """Update or create the dashboard message."""
        try:
            if not channel:
                self.logger.error("Dashboard channel not found")
                return

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

    @app_commands.command(name="update_libraries", description="Update library sections in the dashboard")
    @app_commands.check(is_authorized)
    async def update_libraries(self, interaction: discord.Interaction):
        """Update library sections in the dashboard."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not self.connect_to_jellyfin():
                await interaction.followup.send("❌ Failed to connect to Jellyfin server.", ephemeral=True)
                return

            # Get all libraries
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
                await interaction.followup.send("❌ Failed to fetch libraries from Jellyfin.", ephemeral=True)
                return

            libraries = response.json()
            
            # Update config with new libraries
            self.config["jellyfin_sections"]["sections"] = {}
            
            for library in libraries:
                library_name = library.get("Name", "").lower()
                library_id = library.get("ItemId")
                
                # Find matching emoji based on library name
                emoji = LIBRARY_EMOJIS["default"]
                for key, value in LIBRARY_EMOJIS.items():
                    if key in library_name:
                        emoji = value
                        break
                
                self.config["jellyfin_sections"]["sections"][library_id] = {
                    "display_name": library.get("Name", "Unknown Library"),
                    "emoji": emoji,  # Use the found emoji
                    "color": "#00A4DC",  # Default color
                    "show_episodes": True if any(keyword in library_name for keyword in ["tv", "television", "shows", "series", "anime"]) else False
                }

            # Save updated config
            self.save_config()
            
            # Send initial success message
            await interaction.followup.send("✅ Libraries updated successfully! Refreshing dashboard in 10 seconds...", ephemeral=True)
            
            # Wait 10 seconds
            await asyncio.sleep(10)
            
            # Get server info and update dashboard
            info = await self.get_server_info()
            channel = self.bot.get_channel(self.CHANNEL_ID)
            embed = await self.create_dashboard_embed(info)
            await self._update_dashboard_message(channel, embed)
            
        except Exception as e:
            self.logger.error(f"Error updating libraries: {e}")
            await interaction.followup.send(f"❌ Error updating libraries: {str(e)}", ephemeral=True)

    @app_commands.command(name="episodes", description="Toggle episode numbers display in the dashboard")
    @app_commands.check(is_authorized)
    async def toggle_episodes(self, interaction: discord.Interaction):
        """Toggle episode numbers display in the dashboard."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get current state from any library (they should all be the same)
            current_state = False
            sections = self.config["jellyfin_sections"]["sections"]
            
            if not sections:
                await interaction.followup.send(
                    "⚠️ No libraries are configured yet. Please use `/update_libraries` first.",
                    ephemeral=True
                )
                return
                
            first_library = next(iter(sections.values()))
            current_state = first_library.get("show_episodes", False)
            
            # Log the current state
            self.logger.info(f"Current show_episodes state: {current_state}")
            
            # Toggle the show_episodes setting for all libraries
            new_state = not current_state
            for library_id, library_config in sections.items():
                library_config["show_episodes"] = new_state
                self.logger.info(f"Updated library {library_id} show_episodes to {new_state}")
            
            # Save the updated config
            self.save_config()
            
            # Clear the library cache and force a refresh
            self.library_cache = {}
            self.last_library_update = None
            
            # Get server info and update dashboard
            info = await self.get_server_info()
            channel = self.bot.get_channel(self.CHANNEL_ID)
            embed = await self.create_dashboard_embed(info)
            await self._update_dashboard_message(channel, embed)
            
            await interaction.followup.send(
                f"✅ Episode numbers display has been {'enabled' if new_state else 'disabled'}!",
                ephemeral=True
            )
            
        except Exception as e:
            self.logger.error(f"Error toggling episodes display: {e}")
            await interaction.followup.send(f"❌ Error toggling episodes display: {str(e)}", ephemeral=True)

    @app_commands.command(name="refresh", description="Refresh the dashboard embed immediately")
    @app_commands.check(is_authorized)
    async def refresh_dashboard(self, interaction: discord.Interaction):
        """Refresh the dashboard embed immediately."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get server info and update dashboard
            info = await self.get_server_info()
            channel = self.bot.get_channel(self.CHANNEL_ID)
            embed = await self.create_dashboard_embed(info)
            await self._update_dashboard_message(channel, embed)
            
            await interaction.followup.send("✅ Dashboard refreshed successfully!", ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error refreshing dashboard: {e}")
            await interaction.followup.send(f"❌ Error refreshing dashboard: {str(e)}", ephemeral=True)

    @app_commands.command(name="sync", description="Sync slash commands with Discord")
    @app_commands.check(is_authorized)
    async def sync_commands(self, interaction: discord.Interaction):
        """Sync slash commands with Discord."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Sync the command tree
            await self.bot.tree.sync()
            await interaction.followup.send("✅ Slash commands synced successfully!", ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error syncing commands: {e}")
            await interaction.followup.send(f"❌ Error syncing commands: {str(e)}", ephemeral=True)

    def load_config(self) -> Dict[str, Any]:
        """Load the configuration from config.json."""
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error("Config file not found. Creating default config.")
            default_config = {
                "jellyfin_url": "",
                "jellyfin_api_key": "",
                "dashboard_channel_id": 0,
                "jellyfin_sections": {
                    "sections": {},
                    "show_all": False
                }
            }
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            return default_config
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing config file: {e}")
            raise

    def save_config(self) -> None:
        """Save the current configuration to config.json."""
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving config file: {e}")
            raise

async def setup(bot: commands.Bot) -> None:
    """Add the JellyfinCore cog to the bot."""
    await bot.add_cog(JellyfinCore(bot)) 