import functools
from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    title: str
    artist: str
    video_id: str

    @property
    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.video_id}"


@functools.cache
def _client():
    from ytmusicapi import YTMusic  # imports a web client, so only when music is used

    return YTMusic()  # searching needs no login


def find_song(query: str) -> Song | None:
    """The best matching song on YouTube Music, or None."""
    for result in _client().search(query, filter="songs", limit=3):
        if not result.get("videoId"):
            continue
        artists = result.get("artists") or []
        artist = artists[0]["name"] if artists else "unknown artist"
        return Song(result["title"], artist, result["videoId"])
    return None
