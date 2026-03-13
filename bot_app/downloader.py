import os
import re
import requests
import subprocess
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ---------- LINK DETECTOR ----------
def detect_link_type(url):

    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"

    if "instagram.com" in url:
        return "instagram"

    if "x.com" in url or "twitter.com" in url:
        return "twitter"

    if "spotify.com/track" in url or "spotify.com/playlist" in url:
        return "spotify"

    if url.endswith((".pdf",".doc",".docx",".zip",".mp3",".mp4")):
        return "file"

    return "generic"


# ---------- DOWNLOADERS ----------

def download_youtube(url):
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=1080][vcodec^=avc1]+ba[acodec^=mp4a]/b[height<=1080]",
        "--merge-output-format", "mp4",
        "--recode-video", "mp4",
        "--no-playlist",
        "--restrict-filenames",
        "-o", "%(title)s.%(ext)s",
        "-P", DOWNLOAD_DIR,
        url
    ]
    subprocess.run(cmd)


def download_instagram(url):
    # ---- Try gallery-dl first ----
    cmd = [
        "gallery-dl",
        "--no-mtime",
        "-D", DOWNLOAD_DIR,
        url
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    stderr = (result.stderr or "").lower()

    # ---- If gallery-dl fails → fallback to yt-dlp ----
    if (
        result.returncode != 0
        or "login" in stderr
        or "redirect" in stderr
        or "private" in stderr
    ):
        print("gallery-dl failed → using yt-dlp fallback")
        cmd = [
            "yt-dlp",
            "-f", "best[height<=1080]/best",
            "--restrict-filenames",
            "--no-part",
            "-o", "%(title)s.%(ext)s",
            "-P", DOWNLOAD_DIR,
            url
        ]
        subprocess.run(cmd)


def download_gallery(url):
    cmd = [
        "gallery-dl",
        "-d", DOWNLOAD_DIR,
        url
    ]
    subprocess.run(cmd)


def download_direct(url):

    filename = url.split("/")[-1]

    filepath = os.path.join(DOWNLOAD_DIR, filename)

    r = requests.get(url, stream=True)

    with open(filepath, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def download_spotify(url):

    headers = {"User-Agent": "Mozilla/5.0"}

    success = 0
    failed = 0

    # -------- extract artist + title --------
    def get_track_query(track_url):

        r = requests.get(track_url, headers=headers)
        html = r.text

        title_match = re.search(r'property="og:title" content="([^"]+)"', html)
        artist_match = re.search(r'property="og:description" content="([^"]+)"', html)

        if not title_match:
            return None

        title = title_match.group(1)

        artist = ""
        if artist_match:
            artist = artist_match.group(1).split("·")[0].strip()

        query = f"{artist} - {title}".strip(" -")

        return query


    # -------- download one song --------
    def download_one_song(query, folder):

        cmd = [
            "yt-dlp",
            f"ytsearch1:{query} audio",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--restrict-filenames",
            "--no-playlist",
            "-o", "%(title)s.%(ext)s",
            "-P", folder
        ]

        result = subprocess.run(cmd)

        return result.returncode == 0


    # -------- SINGLE TRACK --------
    if "/track/" in url:

        query = get_track_query(url)

        if not query:
            return "Could not extract track name."

        ok = download_one_song(query, DOWNLOAD_DIR)

        if ok:
            return f"Downloaded: {query}"
        else:
            return f"Failed to download: {query}"


    # -------- PLAYLIST --------
    if "/playlist/" in url:

        r = requests.get(url, headers=headers)
        html = r.text

        # extract playlist name
        name_match = re.search(r'property="og:title" content="([^"]+)"', html)

        playlist_name = "spotify_playlist"
        if name_match:
            playlist_name = re.sub(r'[^\w\s-]', '', name_match.group(1))

        folder = os.path.join(DOWNLOAD_DIR, playlist_name)
        os.makedirs(folder, exist_ok=True)

        # extract track urls
        track_urls = re.findall(
            r'<meta name="music:song" content="(https://open\.spotify\.com/track/[^\"]+)"',
            html
        )

        track_urls = list(dict.fromkeys(track_urls))

        if not track_urls:
            return "Could not extract playlist tracks."

        for track_url in track_urls:

            query = get_track_query(track_url)

            if not query:
                failed += 1
                continue

            ok = download_one_song(query, folder)

            if ok:
                success += 1
            else:
                failed += 1

        return (
            f"Spotify Playlist Downloaded\n\n"
            f"Playlist: {playlist_name}\n"
            f"Total Tracks: {len(track_urls)}\n"
            f"Downloaded: {success}\n"
            f"Failed: {failed}"
        )

    return "Unsupported Spotify link"


# ---------- ROUTER ----------

def handle_download(url):

    link_type = detect_link_type(url)

    if link_type == "youtube":
        download_youtube(url)

    elif link_type == "instagram":
        download_instagram(url)

    elif link_type == "twitter":
        download_gallery(url)

    elif link_type == "spotify":
        return download_spotify(url)

    elif link_type == "file":
        download_direct(url)

    else:
        download_youtube(url)

    return link_type
