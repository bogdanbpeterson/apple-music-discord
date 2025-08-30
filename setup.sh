#!/bin/bash

set -e

echo "Setting up Apple Music Discord Rich Presence..."

# Install the package with uv
echo "Installing package with uv..."
uv tool install -e .

# Copy plist file to LaunchAgents
echo "Copying plist file to LaunchAgents..."
cp com.user.apple-music-discord.plist $HOME/Library/LaunchAgents/

# Load the launch agent
echo "Loading launch agent..."
launchctl load $HOME/Library/LaunchAgents/com.user.apple-music-discord.plist

echo "Setup complete! Apple Music Discord Rich Presence is now installed and will run automatically."
echo "Check logs at /tmp/apple-music-discord.log and /tmp/apple-music-discord-error.log"