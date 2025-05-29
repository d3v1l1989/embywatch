"""
Script to update the test_libraries method in emby_core.py with proper Emby branding
"""
import re

# Path to the file
file_path = "cogs/emby_core.py"

# Read the current content
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# Define the pattern for the test_libraries method
pattern = r'(@app_commands\.command\(name="test-libraries".*?\n.*?await interaction\.followup\.send\(f"❌ Error: {str\(e\)}", ephemeral=True\))'

# Define the replacement with proper Emby branding
replacement = '''@app_commands.command(name="test-libraries", description="Test library statistics retrieval")
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
                value = f"```ansi\\n\\u001b[32mMovies:\\u001b[0m {movie_count}\\n\\u001b[32mSeries:\\u001b[0m {series_count}"
                if stats.get("show_episodes", 0) == 1:
                    value += f"\\n\\u001b[32mEpisodes:\\u001b[0m {episode_count}"
                value += "\\n```"
                    
                embed.add_field(
                    name=f"{emoji} {name}",
                    value=value,
                    inline=True
                )
                
            # Add totals
            embed.add_field(
                name="📊 Totals",
                value=f"```ansi\\n\\u001b[32mMovies:\\u001b[0m {total_movies}\\n\\u001b[32mSeries:\\u001b[0m {total_series}\\n\\u001b[32mEpisodes:\\u001b[0m {total_episodes}\\n```",
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
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)'''

# Replace the method using regex with DOTALL flag to match across lines
updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write the updated content back to the file
with open(file_path, 'w', encoding='utf-8') as file:
    file.write(updated_content)

print("Successfully updated test_libraries method with Emby branding!")
