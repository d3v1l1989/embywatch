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
import aiohttp

# Library name to emoji mapping with priority order
LIBRARY_EMOJIS = {
    # Anime and Cartoons (highest priority)
    "anime": "🎌",
    "anime movies": "🎌",
    "anime series": "🎌",
    "japanese": "🎌",
    "manga": "🎌",
    "cartoons": "🎌",
    "animation": "🎌",
    
    # Movies and Films
    "movies": "🎬",
    "movie": "🎬",
    "films": "🎬",
    "cinema": "🎬",
    "feature": "🎬",
    
    # TV Shows and Series
    "tv": "📺",
    "television": "📺",
    "shows": "📺",
    "series": "📺",
    "episodes": "📺",
    "seasons": "📺",
    
    # Documentaries
    "documentaries": "📽️",
    "docs": "📽️",
    "documentary": "📽️",
    "educational": "📽️",
    "learning": "📽️",
    "science": "🔬",
    "history": "📜",
    "nature": "🌿",
    "wildlife": "🦁",
    
    # Music
    "music": "🎵",
    "songs": "🎵",
    "albums": "🎵",
    "artists": "🎵",
    "playlists": "🎵",
    "audio": "🎵",
    "concerts": "🎤",
    "live": "🎤",
    
    # Books and Audiobooks
    "books": "📚",
    "audiobooks": "📚",
    "literature": "📚",
    "reading": "📚",
    "novels": "📚",
    
    # Photos and Images
    "photos": "📸",
    "pictures": "📸",
    "images": "📸",
    "photography": "📸",
    "gallery": "📸",
    
    # Home Videos
    "home videos": "🎥",
    "videos": "🎥",
    "recordings": "🎥",
    "family videos": "🎥",
    "personal": "🎥",
    
    # Kids and Family
    "kids": "👶",
    "children": "👶",
    "family": "👶",
    "kids movies": "👶",
    "kids shows": "👶",
    "family movies": "👶",
    
    # Sports
    "sports": "⚽",
    "football": "⚽",
    "soccer": "⚽",
    "basketball": "🏀",
    "baseball": "⚾",
    "tennis": "🎾",
    "golf": "⛳",
    "racing": "🏎️",
    "olympics": "🏅",
    "matches": "⚽",
    "games": "🎮",
    
    # Foreign Content
    "foreign": "🌍",
    "international": "🌍",
    "world": "🌍",
    
    # Korean Content
    "korean": "🇰🇷",
    "korea": "🇰🇷",
    "k-drama": "🇰🇷",
    "kdrama": "🇰🇷",
    "kpop": "🇰🇷",
    
    # German Content
    "german": "🇩🇪",
    "deutsch": "🇩🇪",
    "germany": "🇩🇪",
    
    # French Content
    "french": "🇫🇷",
    "france": "🇫🇷",
    "français": "🇫🇷",
    
    # Additional Categories
    "comedy": "😂",
    "standup": "😂",
    "horror": "👻",
    "thriller": "🔪",
    "action": "💥",
    "adventure": "🗺️",
    "drama": "🎭",
    "romance": "💕",
    "scifi": "🚀",
    "fantasy": "🧙",
    "classic": "🎭",
    "indie": "🎨",
    "bollywood": "🎭",
    "hollywood": "🎬",
    "4k": "📺",
    "uhd": "📺",
    "hdr": "📺",
    "dolby": "🎵",
    "atmos": "🎵",
    
    # Default fallback
    "default": "📁"
}

# Generic terms to ignore when more specific content is found
GENERIC_TERMS = {"movies", "movie", "films", "shows", "series", "tv", "television", "videos"}

# Emby brand color: #52B54B (green)
EMBY_GREEN = discord.Color.from_rgb(82, 181, 75)

# Official Emby logo URLs
EMBY_LOGO_LARGE = "https://emby.media/resources/Emby_icon_512.png"
EMBY_LOGO_SMALL = "https://emby.media/resources/Emby_icon_128.png"

RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"

if not RUNNING_IN_DOCKER:
    load_dotenv()

class EmbyCore(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("embywatch_bot.emby")

        # Load environment variables
        self.EMBY_URL = os.getenv("EMBY_URL")
        self.EMBY_API_KEY = os.getenv("EMBY_API_KEY")
        self.EMBY_USERNAME = os.getenv("EMBY_USERNAME")
        self.EMBY_PASSWORD = os.getenv("EMBY_PASSWORD")
        channel_id = os.getenv("CHANNEL_ID")
        
        # Authentication variables
        self.auth_token = None  # Store the auth token from Emby
        self.token_expiry = None  # Token expiration timestamp
        self.user_id = None  # Emby user ID after authentication
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
        self.emby_start_time: Optional[float] = None
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
            "dashboard": {"name": "Emby Dashboard", "icon_url": "", "footer_icon_url": ""},
            "emby_sections": {"show_all": 1, "sections": {}},
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
                # Convert any boolean values to integers
                if "emby_sections" in config:
                    if "show_all" in config["emby_sections"]:
                        config["emby_sections"]["show_all"] = int(config["emby_sections"]["show_all"])
                    if "sections" in config["emby_sections"]:
                        for section in config["emby_sections"]["sections"].values():
                            if "show_episodes" in section:
                                section["show_episodes"] = int(section["show_episodes"])
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

    async def connect_to_emby(self) -> bool:
        """Attempt to establish a connection to the Emby server.
        
        This method handles authentication with the Emby server using either an API key
        or username/password credentials. It stores the authentication token for reuse
        and handles token renewal when needed.
        """
        try:
            # Check if we have a valid cached token
            current_time = time.time()
            if self.auth_token and self.token_expiry and current_time < self.token_expiry:
                return True
                
            # Common headers for all requests
            headers = {
                "X-Emby-Client": "EmbyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "EmbyWatch",
                "X-Emby-Device-Id": "embywatch-bot",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"EmbyWatch\", Device=\"EmbyWatch\", DeviceId=\"embywatch-bot\", Version=\"1.0.0\""
            }

            # First try with API key if available
            if self.EMBY_API_KEY:
                headers["X-Emby-Token"] = self.EMBY_API_KEY
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.EMBY_URL}/System/Info", headers=headers) as response:
                        if response.status == 200:
                            self.auth_token = self.EMBY_API_KEY
                            # API keys don't expire
                            self.token_expiry = float('inf')
                            if self.emby_start_time is None:
                                self.emby_start_time = time.time()
                            self.logger.info("Successfully connected to Emby server using API key")
                            return True
                        elif response.status == 401:
                            self.logger.error("Invalid API key provided")
                            self.auth_token = None
                            return False
                        else:
                            self.logger.error(f"Failed to connect with API key: HTTP {response.status}")
                            return False

            # If API key fails or not available, try username/password
            if self.EMBY_USERNAME and self.EMBY_PASSWORD:
                auth_data = {
                    "Username": self.EMBY_USERNAME,
                    "Pw": self.EMBY_PASSWORD
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.EMBY_URL}/Users/AuthenticateByName",
                        json=auth_data,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            # Parse authentication response
                            auth_response = await response.json()
                            self.auth_token = auth_response.get("AccessToken")
                            self.user_id = auth_response.get("User", {}).get("Id")
                            
                            # Store token with expiration time (default 30 days)
                            # Emby doesn't explicitly return token expiry, so we set our own reasonable duration
                            self.token_expiry = time.time() + (30 * 24 * 60 * 60)  # 30 days in seconds
                            
                            if self.emby_start_time is None:
                                self.emby_start_time = time.time()
                                
                            self.logger.info(f"Successfully authenticated with Emby server as {self.EMBY_USERNAME}")
                            return True
                        elif response.status == 401:
                            self.logger.error("Invalid username or password")
                            self.auth_token = None
                            return False
                        else:
                            error_body = await response.text()
                            self.logger.error(f"Failed to authenticate with username/password: HTTP {response.status}")
                            self.logger.error(f"Error response: {error_body}")
                            return False

            self.logger.error("No authentication method provided (API key or username/password required)")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Emby server: {e}", exc_info=True)
            self.emby_start_time = None
            self.auth_token = None
            return False

    @tasks.loop(seconds=30)
    async def update_status(self) -> None:
        """Update bot's status with current stream count."""
        try:
            sessions = await self.get_sessions()
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
        """Get server information from Emby.
        
        Retrieves general server information, session counts, and library statistics.
        Uses cached auth token and follows Emby API specifications.
        """
        try:
            # Ensure we're authenticated
            if not await self.connect_to_emby():
                self.logger.error("Failed to connect to Emby server")
                return {}

            # Use the stored auth token
            headers = {
                "X-Emby-Token": self.auth_token,
                "X-Emby-Client": "EmbyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "EmbyWatch",
                "X-Emby-Device-Id": "embywatch-bot",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"EmbyWatch\", Device=\"EmbyWatch\", DeviceId=\"embywatch-bot\", Version=\"1.0.0\""
            }

            async with aiohttp.ClientSession() as session:
                # Get system info
                async with session.get(f"{self.EMBY_URL}/System/Info", headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to get system info: HTTP {response.status}")
                        return {}
                    system_info = await response.json()
                    self.logger.debug(f"Retrieved Emby system info: {system_info.get('ServerName')}")
                
                # Get sessions
                sessions = await self.get_sessions()
                current_streams = len([s for s in sessions if s.get("NowPlayingItem")]) if sessions else 0

                # Get library stats
                library_stats = await self.get_library_stats()
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
            self.logger.error(f"Error getting server info: {e}", exc_info=True)
            return {}

    def calculate_uptime(self) -> str:
        """Calculate Emby server uptime as a formatted string."""
        if not self.emby_start_time:
            return "Offline"
        total_minutes = int((time.time() - self.emby_start_time) / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return "99+ Hours" if hours > 99 else f"{hours:02d}:{minutes:02d}"

    async def get_library_stats(self) -> Dict[str, Dict[str, Any]]:
        """Fetch and cache Emby library statistics.
        
        This method retrieves information about all libraries in the Emby server,
        including counts of movies, series, and episodes. Results are cached to
        minimize API calls.
        """
        current_time = datetime.now()
        # Return cached results if within update interval
        if (
            self.last_library_update
            and (current_time - self.last_library_update).total_seconds() <= self.library_update_interval
        ):
            return self.library_cache

        # Ensure we're authenticated
        if not await self.connect_to_emby():
            self.logger.warning("Using cached library stats due to authentication failure")
            return self.library_cache

        try:
            # Use the stored auth token
            headers = {
                "X-Emby-Token": self.auth_token,
                "X-Emby-Client": "EmbyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "EmbyWatch",
                "X-Emby-Device-Id": "embywatch-bot",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"EmbyWatch\", Device=\"EmbyWatch\", DeviceId=\"embywatch-bot\", Version=\"1.0.0\""
            }
        
            async with aiohttp.ClientSession() as session:
                # Get all libraries from Emby
                async with session.get(f"{self.EMBY_URL}/Library/VirtualFolders", headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to get library folders: HTTP {response.status}")
                        return self.library_cache
                    libraries = await response.json()
                    self.logger.debug(f"Retrieved {len(libraries)} libraries from Emby")

                stats: Dict[str, Dict[str, Any]] = {}
                emby_config = self.config["emby_sections"]
                configured_sections = emby_config["sections"]

                for library in libraries:
                    library_id = library.get("ItemId")
                    library_name = library.get("Name", "").lower()
                    
                    # Skip libraries that aren't configured if show_all is disabled
                    if not int(emby_config["show_all"]) and library_id not in configured_sections:
                        self.logger.debug(f"Skipping library {library_name} (not in configured sections)")
                        continue

                    # Get library configuration or use defaults
                    config = configured_sections.get(library_id, {
                        "display_name": library.get("Name", "Unknown Library"),
                        "emoji": LIBRARY_EMOJIS.get("default", "📁"),
                        "show_episodes": 0
                    })

                    # Get appropriate emoji based on library name
                    if "emoji" not in config or not config["emoji"]:
                        config["emoji"] = self._get_library_emoji(library_name)

                    # Use the configured emoji
                    emoji = config.get("emoji", "📁")

                    # Get item counts for this library
                    params = {
                        "ParentId": library_id,
                        "Recursive": "true",
                        "IncludeItemTypes": "Movie,Series,Episode",
                        "Fields": "BasicSyncInfo,MediaSources"
                    }
                    async with session.get(
                        f"{self.EMBY_URL}/Items",
                        headers=headers,
                        params=params
                    ) as items_response:
                        if items_response.status == 200:
                            items = await items_response.json()
                            
                            # Count items by type
                            movie_count = sum(1 for item in items["Items"] if item["Type"] == "Movie")
                            series_count = sum(1 for item in items["Items"] if item["Type"] == "Series")
                            episode_count = sum(1 for item in items["Items"] if item["Type"] == "Episode")
                            
                            self.logger.debug(f"Library {library_name}: {movie_count} movies, {series_count} series, {episode_count} episodes")

                            # Create base stats dictionary
                            library_stats = {
                                "count": movie_count + series_count,
                                "movie_count": movie_count,
                                "series_count": series_count,
                                "display_name": config.get("display_name", library.get("Name", "Unknown Library")),
                                "emoji": emoji,
                                "show_episodes": int(config.get("show_episodes", 0))  # Ensure integer
                            }

                            # Only add episodes if show_episodes is 1
                            if int(config.get("show_episodes", 0)) == 1:
                                library_stats["episodes"] = episode_count

                            stats[library_id] = library_stats
                        else:
                            # Get the response body for more detailed error information
                            error_body = await items_response.text()
                            self.logger.error(f"Failed to get items for library {library_name}: HTTP {items_response.status}")
                            self.logger.error(f"Error response body: {error_body}")
                            self.logger.error(f"Request URL: {items_response.url}")

                # Update cache and timestamp
                self.library_cache = stats
                self.last_library_update = current_time
                self.logger.info(f"Library stats updated and cached (interval: {self.library_update_interval}s)")
                return stats
        except Exception as e:
            self.logger.error(f"Error getting library stats: {e}", exc_info=True)
            return self.library_cache

    def _get_library_emoji(self, library_name: str) -> str:
        """Get the appropriate emoji for a library based on its name.
        
        This method analyzes the library name and selects the most specific
        emoji from the LIBRARY_EMOJIS mapping based on keyword matching.
        """
        library_name = library_name.lower()
        
        # First look for exact matches
        if library_name in LIBRARY_EMOJIS:
            return LIBRARY_EMOJIS[library_name]
            
        # Then look for partial matches by priority (non-generic terms first)
        best_match = None
        for term in LIBRARY_EMOJIS:
            # Skip generic terms if we already have a more specific match
            if term in GENERIC_TERMS and best_match is not None:
                continue
                
            if term in library_name and (best_match is None or term not in GENERIC_TERMS):
                best_match = term
                
        # Return the best match or default
        return LIBRARY_EMOJIS.get(best_match or "default", "📁")

    @app_commands.command(name="test-libraries", description="Test Emby library statistics retrieval")
    @app_commands.check(is_authorized)
    async def test_libraries(self, interaction: discord.Interaction):
        """Test the library statistics retrieval from Emby."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get library stats
            library_stats = await self.get_library_stats()
            
            if not library_stats:
                await interaction.followup.send("❌ Failed to retrieve library statistics.", ephemeral=True)
                return
                
            # Create an embed to display the results
            embed = discord.Embed(
                title="📚 Emby Library Statistics",
                description=f"Found {len(library_stats)} libraries",
                color=EMBY_GREEN
            )
            # Set thumbnail to official Emby logo
            embed.set_thumbnail(url=EMBY_LOGO_LARGE)
            
            total_movies = 0
            total_series = 0
            total_episodes = 0
            
            # Add each library to the embed
            for library_id, stats in library_stats.items():
                emoji = stats.get("emoji", "📁")
                name = stats.get("display_name", "Unknown Library")
                movie_count = stats.get("movie_count", 0)
                series_count = stats.get("series_count", 0)
                episode_count = stats.get("episodes", 0)
                
                total_movies += movie_count
                total_series += series_count
                total_episodes += episode_count
                
                # Create field value with ANSI color coding
                value = f"```ansi\n\u001b[32mMovies:\u001b[0m {movie_count}\n\u001b[32mSeries:\u001b[0m {series_count}"
                if stats.get("show_episodes", 0) == 1:
                    value += f"\n\u001b[32mEpisodes:\u001b[0m {episode_count}"
                value += "\n```"
                
                embed.add_field(
                    name=f"{emoji} {name}",
                    value=value,
                    inline=True
                )
                
            # Add totals
            embed.add_field(
                name="📊 Totals",
                value=f"```ansi\n\u001b[32mMovies:\u001b[0m {total_movies}\n\u001b[32mSeries:\u001b[0m {total_series}\n\u001b[32mEpisodes:\u001b[0m {total_episodes}\n```",
                inline=False
            )
            
            # Set footer with EmbyWatch branding and timestamp
            current_time = datetime.now().strftime("%H:%M:%S")
            embed.set_footer(
                text=f"Powered by EmbyWatch | {current_time}",
                icon_url=EMBY_LOGO_SMALL
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error testing library stats: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    def get_offline_info(self) -> Dict[str, Any]:
        """Return offline status information."""
        if self.offline_since is None:
            self.offline_since = datetime.now()
        
        offline_duration = datetime.now() - self.offline_since
        hours = int(offline_duration.total_seconds() / 3600)
        minutes = int((offline_duration.total_seconds() % 3600) / 60)
        
        # Convert any boolean values in library_cache to integers
        library_stats = {}
        for library_id, stats in self.library_cache.items():
            library_stats[library_id] = {
                "count": int(stats.get("count", 0)),
                "display_name": stats.get("display_name", "Unknown Library"),
                "emoji": stats.get("emoji", "📁"),
                "show_episodes": int(stats.get("show_episodes", 0))
            }
            if "episodes" in stats:
                library_stats[library_id]["episodes"] = int(stats["episodes"])
        
        return {
            "status": "🔴 Offline",
            "uptime": f"Offline for {hours:02d}:{minutes:02d}",
            "library_stats": library_stats,
            "active_users": [],
            "current_streams": [],
        }

    async def create_dashboard_embed(self, info: Dict[str, Any]) -> discord.Embed:
        """Create the dashboard embed with server information."""
        embed = discord.Embed(
            title=f"📺 {info.get('server_name', 'Emby Server')}",
            description="Real-time server status and statistics",
            color=EMBY_GREEN
        )
        
        # Set thumbnail to official Emby logo
        embed.set_thumbnail(url=EMBY_LOGO_LARGE)
        
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
            value=f"```ansi\n\u001b[32m{current_streams} active stream{'s' if current_streams != 1 else ''}\u001b[0m\n```",
            inline=False
        )
        
        # Add library statistics
        library_stats = info.get('library_stats', {})
        if library_stats:
            # Sort libraries by display_name
            sorted_libraries = sorted(
                library_stats.items(),
                key=lambda x: x[1].get('display_name', '').lower()
            )
            
            stats_text = ""
            for library_id, stats in sorted_libraries:
                if stats.get('count', 0) > 0:  # Only show libraries with items
                    stats_text += f"{stats.get('emoji', '📁')} **{stats.get('display_name', 'Unknown Library')}**\n"
                    stats_text += f"```ansi\n\u001b[32mTotal Items: {stats.get('count', 0)}\u001b[0m\n```\n"
                    # Only show episodes if show_episodes is 1 and episodes count exists
                    if int(stats.get('show_episodes', 0)) == 1 and 'episodes' in stats:
                        stats_text += f"```ansi\n\u001b[32mEpisodes: {stats['episodes']}\u001b[0m\n```\n"
            if stats_text:  # Only add the field if there are libraries to show
                embed.add_field(
                    name="Library Statistics",
                    value=stats_text,
                    inline=False
                )
        
        # Set footer with EmbyWatch branding and timestamp
        current_time = datetime.now().strftime("%H:%M:%S")
        embed.set_footer(
            text=f"Powered by EmbyWatch | Last updated at {current_time}",
            icon_url=EMBY_LOGO_SMALL
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

    @app_commands.command(name="update_libraries", description="Update Emby library sections in the dashboard")
    @app_commands.check(is_authorized)
    async def update_libraries(self, interaction: discord.Interaction):
        """Update library sections in the dashboard."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not await self.connect_to_emby():
                await interaction.followup.send("❌ Failed to connect to Emby server.", ephemeral=True)
                return

            # Get all libraries
            headers = {
                "X-Emby-Token": self.EMBY_API_KEY,
                "X-Emby-Client": "EmbyWatch",
                "X-Emby-Client-Version": "1.0.0",
                "X-Emby-Device-Name": "EmbyWatch",
                "X-Emby-Device-Id": "embywatch-bot",
                "Accept": "application/json",
                "X-Emby-Authorization": "MediaBrowser Client=\"EmbyWatch\", Device=\"EmbyWatch\", DeviceId=\"embywatch-bot\", Version=\"1.0.0\""
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.EMBY_URL}/Library/VirtualFolders", headers=headers) as response:
                    if response.status != 200:
                        await interaction.followup.send("❌ Failed to fetch libraries from Emby.", ephemeral=True)
                        return

                    libraries = await response.json()
            
            # Sort libraries by name
            libraries = sorted(libraries, key=lambda x: x.get("Name", "").lower())
            
            # Update config with new libraries
            self.config["emby_sections"]["sections"] = {}
            
            for library in libraries:
                library_name = library.get("Name", "").lower()
                library_id = library.get("ItemId")
                
                # Find matching emoji based on library name with priority
                emoji = LIBRARY_EMOJIS["default"]
                best_match_length = 0
                best_match_key = None
                
                # First pass: find all matches
                matches = []
                library_name_lower = library_name.lower()
                for key, value in LIBRARY_EMOJIS.items():
                    if key == "default":
                        continue
                    if key in library_name_lower:
                        matches.append((key, value, len(key), key in GENERIC_TERMS))
                
                # Second pass: find the best non-generic match
                for key, value, length, is_generic in matches:
                    if not is_generic and length > best_match_length:
                        best_match_length = length
                        best_match_key = key
                        emoji = value
                
                # If no non-generic match was found, use the best match overall
                if best_match_key is None and matches:
                    best_match_length = max(length for _, _, length, _ in matches)
                    for key, value, length, _ in matches:
                        if length == best_match_length:
                            emoji = value
                            break
                
                # Log the emoji selection for debugging
                self.logger.debug(f"Library '{library_name}' matched with emoji '{emoji}' (best match: '{best_match_key}')")
                
                # Always set show_episodes to 0 by default
                show_episodes = 0
                
                self.config["emby_sections"]["sections"][library_id] = {
                    "display_name": library.get("Name", "Unknown Library"),
                    "emoji": emoji,
                    "color": EMBY_GREEN,  # Emby green color
                    "show_episodes": show_episodes  # Use integer instead of boolean
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

    @app_commands.command(name="episodes", description="Toggle Emby episode numbers display in the dashboard")
    @app_commands.check(is_authorized)
    async def toggle_episodes(self, interaction: discord.Interaction):
        """Toggle episode numbers display in the dashboard."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get current state from any library (they should all be the same)
            current_state = 0
            sections = self.config["emby_sections"]["sections"]
            
            if not sections:
                await interaction.followup.send(
                    "⚠️ No libraries are configured yet. Please use `/update_libraries` first.",
                    ephemeral=True
                )
                return
                
            first_library = next(iter(sections.values()))
            current_state = int(first_library.get("show_episodes", 0))  # Ensure integer
            
            # Log the current state
            self.logger.info(f"Current show_episodes state: {current_state}")
            
            # Toggle the show_episodes setting for all libraries
            new_state = 1 if current_state == 0 else 0
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
                f"✅ Episode numbers display has been {'enabled' if new_state == 1 else 'disabled'}!",
                ephemeral=True
            )
            
        except Exception as e:
            self.logger.error(f"Error toggling episodes display: {e}")
            await interaction.followup.send(f"❌ Error toggling episodes display: {str(e)}", ephemeral=True)

    @app_commands.command(name="refresh", description="Refresh the Emby dashboard embed immediately")
    @app_commands.check(is_authorized)
    async def refresh_dashboard(self, interaction: discord.Interaction):
        """Refresh the dashboard embed immediately."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            self.logger.info("Starting dashboard refresh...")
            
            # Get server info and update dashboard
            self.logger.info("Attempting to get server info...")
            info = await self.get_server_info()
            if not info:
                self.logger.error("Failed to get server info - empty response")
                await interaction.followup.send("❌ Failed to get server information. Check bot logs for details.", ephemeral=True)
                return
                
            self.logger.info(f"Got server info: {info.get('server_name', 'Unknown Server')}")
            
            self.logger.info(f"Getting channel with ID: {self.CHANNEL_ID}")
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if not channel:
                self.logger.error(f"Channel {self.CHANNEL_ID} not found")
                await interaction.followup.send("❌ Dashboard channel not found. Check CHANNEL_ID in config.", ephemeral=True)
                return
                
            self.logger.info("Creating dashboard embed...")
            embed = await self.create_dashboard_embed(info)
            
            self.logger.info("Updating dashboard message...")
            await self._update_dashboard_message(channel, embed)
            
            self.logger.info("Dashboard refresh completed successfully")
            await interaction.followup.send("✅ Dashboard refreshed successfully!", ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error refreshing dashboard: {str(e)}", exc_info=True)
            await interaction.followup.send(f"❌ Error refreshing dashboard: {str(e)}", ephemeral=True)

    @app_commands.command(name="test_connection", description="Test connection to the Emby server")
    @app_commands.check(is_authorized)
    async def test_connection(self, interaction: discord.Interaction):
        """Test connection to the Emby server and return status information."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            self.logger.info(f"Testing connection to Emby server at {self.EMBY_URL}")
            start_time = time.time()
            connection_successful = await self.connect_to_emby()
            response_time = round((time.time() - start_time) * 1000)  # ms
            
            if connection_successful:
                # Get basic server info
                headers = {
                    "X-Emby-Token": self.auth_token,
                    "X-Emby-Client": "EmbyWatch",
                    "X-Emby-Client-Version": "1.0.0",
                    "X-Emby-Device-Name": "EmbyWatch",
                    "X-Emby-Device-Id": "embywatch-bot",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.EMBY_URL}/System/Info", headers=headers) as response:
                        if response.status == 200:
                            system_info = await response.json()
                            embed = discord.Embed(
                                title="✅ Emby Server Connection Test",
                                description=f"Successfully connected to Emby server",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Server Name", value=system_info.get("ServerName", "Unknown"), inline=True)
                            embed.add_field(name="Version", value=system_info.get("Version", "Unknown"), inline=True)
                            embed.add_field(name="Operating System", value=system_info.get("OperatingSystem", "Unknown"), inline=True)
                            embed.add_field(name="Response Time", value=f"{response_time}ms", inline=True)
                            embed.add_field(name="Auth Method", value="API Key" if self.auth_token == self.EMBY_API_KEY else "User Credentials", inline=True)
                            embed.set_footer(text=f"Emby URL: {self.EMBY_URL}")
                            
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            self.logger.info(f"Connection test successful - Server: {system_info.get('ServerName')}")
                            return
                
                # Basic success response if we couldn't get system info
                await interaction.followup.send(f"✅ Successfully connected to Emby server at {self.EMBY_URL} (Response time: {response_time}ms)", ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Emby Server Connection Failed",
                    description=f"Could not connect to Emby server at {self.EMBY_URL}",
                    color=discord.Color.red()
                )
                embed.add_field(name="Possible Issues", value="• Incorrect server URL\n• Invalid API key\n• Invalid username/password\n• Server is offline\n• Network connectivity issues", inline=False)
                embed.add_field(name="Response Time", value=f"{response_time}ms", inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                self.logger.error(f"Connection test failed - URL: {self.EMBY_URL}")
        except Exception as e:
            self.logger.error(f"Error testing connection: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error testing connection: {str(e)}", ephemeral=True)

    @app_commands.command(name="sync", description="Sync Emby dashboard slash commands with Discord")
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
                "emby_url": "",
                "emby_api_key": "",
                "dashboard_channel_id": 0,
                "emby_sections": {
                    "sections": {},
                    "show_all": 1
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
            # Create a copy of the config to modify
            config_to_save = {
                "dashboard": self.config.get("dashboard", {}),
                "emby_sections": {
                    "show_all": int(self.config.get("emby_sections", {}).get("show_all", 1)),
                    "sections": {}
                },
                "presence": self.config.get("presence", {}),
                "cache": self.config.get("cache", {})
            }
            
            # Convert any boolean values to integers in sections
            for library_id, section in self.config.get("emby_sections", {}).get("sections", {}).items():
                config_to_save["emby_sections"]["sections"][library_id] = {
                    "display_name": section.get("display_name", "Unknown Library"),
                    "emoji": section.get("emoji", "📁"),
                    "color": section.get("color", "#00A4DC"),
                    "show_episodes": int(section.get("show_episodes", 0))
                }
            
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving config file: {e}")
            raise

    # Duplicate test-libraries command removed from here

async def setup(bot: commands.Bot) -> None:
    """Add the EmbyCore cog to the bot."""
    await bot.add_cog(EmbyCore(bot))