"""
EmbyWatch Dashboard Updates

This file contains updated dashboard and display components for Phase 4 of the EmbyWatch project.
The code here is designed to be integrated into the main codebase to update Jellyfin references
with Emby branding and theming.

Key changes:
- Updated color scheme to use Emby green (#52B54B)
- Added official Emby logos
- Enhanced visual display with ANSI formatting
- Consistent branding across all components

Implementation Status:
- Updated the create_dashboard_embed method with Emby branding ✅
- Enhanced library statistics formatting with ANSI colors ✅
- Added test_libraries method below for reference ✅
"""

import discord
from datetime import datetime
from typing import Dict, Any

# Emby brand color: #52B54B (green)
EMBY_GREEN = discord.Color.from_rgb(82, 181, 75)

# Official Emby logo URLs
EMBY_LOGO_LARGE = "https://emby.media/resources/Emby_icon_512.png"
EMBY_LOGO_SMALL = "https://emby.media/resources/Emby_icon_128.png"

async def create_dashboard_embed(info: Dict[str, Any]) -> discord.Embed:
    """Create the dashboard embed with server information using Emby theming."""
    embed = discord.Embed(
        title=f"📺 {info.get('server_name', 'Emby Server')}",
        description="Real-time server status and statistics",
        color=EMBY_GREEN
    )
    
    # Set thumbnail to official Emby logo
    embed.set_thumbnail(url=EMBY_LOGO_LARGE)
    
    # Add server status
    status = "🟢 Online" if info else "🔴 Offline"
    uptime = info.get('uptime', 'Unknown')
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

async def create_library_test_embed(library_stats: Dict) -> discord.Embed:
    """Create an embed for testing library statistics with Emby theming."""
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
    
    return embed
