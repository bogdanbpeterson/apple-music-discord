#!/usr/bin/env python3
import socket
import json
import struct
import os
import subprocess
import time
import uuid
import urllib.error
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from email.message import Message


@dataclass
class SongData:
    title: str
    artist: str
    album: str
    duration: float
    position: float
    url: Optional[str] = None

    def __post_init__(self):
        # Validate numeric values
        if self.duration < 0:
            raise ValueError("Duration must be non-negative")
        if self.position < 0:
            raise ValueError("Position must be non-negative")
        if self.position > self.duration:
            self.position = self.duration  # Cap position at duration

        # Validate string fields
        if not self.title.strip():
            raise ValueError("Title cannot be empty")
        if not self.artist.strip():
            raise ValueError("Artist cannot be empty")


class DiscordRPC:
    def __init__(self, client_id: str):
        if not client_id or not client_id.strip():
            raise ValueError("Client ID cannot be empty")
        if not client_id.isdigit():
            raise ValueError("Client ID must be numeric")

        self.client_id: str = client_id
        self.sock: Optional[socket.socket] = None
        self.connected: bool = False

    def connect(self) -> bool:
        """Connect to Discord IPC"""
        if self.connected:
            return True

        tmpdir = os.environ.get("TMPDIR", "/tmp/")

        if not os.path.exists(tmpdir):
            return False

        for i in range(10):
            try:
                socket_path = os.path.join(tmpdir, f"discord-ipc-{i}")
                if not os.path.exists(socket_path):
                    continue

                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)  # Add timeout
                self.sock.connect(socket_path)

                # Send handshake
                handshake: Dict[str, Union[int, str]] = {
                    "v": 1,
                    "client_id": self.client_id,
                }
                self._send_packet(0, handshake)

                # Read response
                _, response = self._read_packet()
                if response and response.get("evt") == "READY":
                    self.connected = True
                    return True

            except (OSError, socket.error, json.JSONDecodeError, struct.error):
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
                continue
            except Exception:
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
                continue

        return False

    def _send_packet(self, opcode: int, data: Dict[str, Any]) -> None:
        """Send a properly formatted Discord IPC packet"""
        if not self.sock:
            raise RuntimeError("Socket not connected")
        if opcode < 0:
            raise ValueError("Opcode must be a non-negative integer")

        try:
            json_data = json.dumps(data).encode("utf-8")
            header = struct.pack("<II", opcode, len(json_data))
            self.sock.send(header + json_data)
        except (struct.error, OSError) as e:
            raise RuntimeError(f"Failed to send packet: {e}")

    def _read_packet(self) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Read a Discord IPC packet"""
        if not self.sock:
            return None, None

        try:
            header = self.sock.recv(8)
            if len(header) < 8:
                return None, None

            opcode, length = struct.unpack("<II", header)

            # Validate packet length
            if length > 1024 * 1024:  # 1MB limit
                raise ValueError("Packet too large")
            if length <= 0:
                raise ValueError("Invalid packet length")

            data = self.sock.recv(length).decode("utf-8")
            return opcode, json.loads(data)

        except (struct.error, json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None, None

    def set_activity(self, activity: Optional[Dict[str, Any]] = None) -> bool:
        """Set Discord activity (Rich Presence)"""
        if not self.connected or not self.sock:
            return False

        try:
            command: Dict[str, Any] = {
                "cmd": "SET_ACTIVITY",
                "nonce": str(uuid.uuid4()),
                "args": {"pid": os.getpid(), "activity": activity},
            }

            self._send_packet(1, command)  # FRAME opcode

            # Read Discord's response
            _, response = self._read_packet()

            if response and response.get("evt") == "ERROR":
                return False

            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close Discord connection"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self.connected = False


def get_album_artwork(artist: str, title: str, album: str) -> Optional[str]:
    """Get album artwork URL from Deezer API"""
    if not artist.strip() and not title.strip():
        return None

    try:
        # Search query - prioritize artist and title
        query = f"{artist} {title}".strip()
        if not query:
            return None

        encoded_query = urllib.parse.quote(query)

        # Search Deezer API
        url = f"https://api.deezer.com/search/track?q={encoded_query}&limit=1"

        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                return None

            data = json.loads(response.read().decode())

            if data.get("data") and len(data["data"]) > 0:
                track = data["data"][0]
                album_info = track.get("album", {})

                # Return the largest available cover
                return (
                    album_info.get("cover_xl")
                    or album_info.get("cover_big")
                    or album_info.get("cover_medium")
                )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        KeyError,
        TimeoutError,
    ):
        pass
    except Exception:
        pass

    return None


def get_apple_music_url(artist: str, title: str, album: str) -> str:
    """Get actual Apple Music song URL using iTunes Search API"""
    if not artist.strip() and not title.strip():
        return "https://music.apple.com/"

    try:
        # First try searching with artist and title
        query = f"{title} {artist}".strip()
        if not query:
            return "https://music.apple.com/"

        encoded_query = urllib.parse.quote(query)

        # Search iTunes API
        url = f"https://itunes.apple.com/search?term={encoded_query}&media=music&entity=song&limit=5"

        with urllib.request.urlopen(url, timeout=5) as response:
            msg = Message()
            if response.status != 200:
                raise urllib.error.HTTPError(
                    url,
                    response.status,
                    "HTTP Error",
                    msg,
                    None,
                )

            data = json.loads(response.read().decode())

            if data.get("results"):
                # Look for best match based on artist and title similarity
                for result in data["results"]:
                    result_artist = result.get("artistName", "").lower()
                    result_title = result.get("trackName", "").lower()

                    # Check if artist and title match (case insensitive)
                    if (
                        artist.lower() in result_artist
                        or result_artist in artist.lower()
                    ) and (
                        title.lower() in result_title or result_title in title.lower()
                    ):
                        track_view_url = result.get("trackViewUrl")
                        if track_view_url and isinstance(track_view_url, str):
                            # Convert iTunes URL to Apple Music URL
                            apple_music_url = track_view_url.replace(
                                "itunes.apple.com", "music.apple.com"
                            )
                            return apple_music_url

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        KeyError,
        TimeoutError,
    ):
        pass
    except Exception:
        pass

    # Fallback to search URL
    fallback_query = f"{artist} {title}".strip()
    if fallback_query:
        encoded_fallback = urllib.parse.quote(fallback_query)
        return f"https://music.apple.com/search?term={encoded_fallback}"

    return "https://music.apple.com/"


def get_current_song() -> Optional[SongData]:
    """Get currently playing song from Apple Music"""
    applescript = """
   tell application "Music"
       if player state is playing then
           set trackName to name of current track
           set artistName to artist of current track
           set albumName to album of current track
           set trackDuration to duration of current track
           set playerPos to player position
           set trackUrl to ""
           
           -- Note: We'll use iTunes Search API instead of persistent ID
           set trackUrl to ""
           
           return trackName & "|||" & artistName & "|||" & albumName & "|||" & trackDuration & "|||" & playerPos & "|||" & trackUrl
       else
           return "NOT_PLAYING"
       end if
   end tell
   """

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,  # Add timeout
        )

        output = result.stdout.strip()
        if not output or output == "NOT_PLAYING":
            return None

        parts = output.split("|||")
        if len(parts) < 5:
            return None

        # Validate and convert data
        try:
            duration = float(parts[3])
            position = float(parts[4])
        except (ValueError, IndexError):
            return None

        song_data = SongData(
            title=parts[0].strip(),
            artist=parts[1].strip(),
            album=parts[2].strip(),
            duration=duration,
            position=position,
        )

        # Add URL if available (6th part)
        if len(parts) >= 6 and parts[5].strip():
            song_data.url = parts[5].strip()

        return song_data

    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        OSError,
    ):
        pass
    except Exception:
        pass

    return None


def main() -> None:
    # Your Discord application ID
    CLIENT_ID = "1410325920039960657"

    try:
        discord = DiscordRPC(CLIENT_ID)
    except ValueError as e:
        print(f"Error: {e}")
        return

    if not discord.connect():
        print("Failed to connect to Discord")
        return

    last_was_playing: Optional[bool] = None
    last_song_info: Optional[str] = None
    cached_artwork: Optional[str] = None

    try:
        while True:
            song = get_current_song()

            if song:
                # Check if song changed
                current_song_info = f"{song.artist}-{song.title}"
                if current_song_info != last_song_info:
                    cached_artwork = get_album_artwork(
                        song.artist, song.title, song.album
                    )
                    last_song_info = current_song_info

                # Use real Apple Music URL if available, otherwise use iTunes Search API
                apple_music_url = song.url or get_apple_music_url(
                    song.artist, song.title, song.album
                )

                current_time = int(time.time())
                start_time = current_time - int(song.position)
                end_time = current_time + int(song.duration - song.position)

                activity: Dict[str, Any] = {
                    "type": 2,  # ActivityType.Listening
                    "name": "Apple Music",  # Explicit app name
                    "details": song.title,
                    "state": f"by {song.artist}",
                    "timestamps": {
                        "start": start_time,
                        "end": end_time,
                    },
                    "buttons": [
                        {"label": "Listen on Apple Music", "url": apple_music_url}
                    ],
                }

                # Add album artwork if found
                if cached_artwork:
                    activity["assets"] = {
                        "large_image": cached_artwork,
                        "large_text": f"{song.album} by {song.artist}",
                    }

                discord.set_activity(activity)
                last_was_playing = True

            else:
                # No song playing - clear activity once
                if last_was_playing is not False:
                    discord.set_activity(None)  # Clear activity
                    last_was_playing = False

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        discord.set_activity(None)  # Clear on exit
        discord.close()


if __name__ == "__main__":
    main()
