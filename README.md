# Apple Music Discord Rich Presence

Apple Music Discord Rich Presence integration for macOS.

## TODO

- [ ] Prevent script fail if discord isn't opened (needs debugging)
- [ ] Add a config file
  - [ ] Allow to show paused state instead of removing the activity altogether

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- macOS
- Discord

## Installation

Run the setup script:

```bash
chmod +x setup.sh
./setup.sh
```

This will:

1. Install the package using `uv tool install -e .`
2. Copy the launch agent plist file to `$HOME/Library/LaunchAgents/`
3. Load the launch agent with `launchctl`

The service will start automatically and run in the background.

## Manual Installation

If you prefer to install manually:

```bash
# Install the package
uv tool install -e .

# Copy the plist file
cp com.user.apple-music-discord.plist $HOME/Library/LaunchAgents/

# Load the launch agent
launchctl load $HOME/Library/LaunchAgents/com.user.apple-music-discord.plist
```

## Usage

The service runs automatically in the background once installed. It will display your currently playing Apple Music track as Discord rich presence.

## Logs

Check the logs for troubleshooting:

- Standard output: `/tmp/apple-music-discord.log`
- Error output: `/tmp/apple-music-discord-error.log`

## Uninstalling

To stop and remove the service:

```bash
# Unload the launch agent
launchctl unload $HOME/Library/LaunchAgents/com.user.apple-music-discord.plist

# Remove the plist file
rm $HOME/Library/LaunchAgents/com.user.apple-music-discord.plist

# Uninstall the package
uv tool uninstall apple-music-discord
```
