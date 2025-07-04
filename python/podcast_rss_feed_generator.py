#!/usr/bin/env python3
"""
Generate the RSS feed from a directory of MP3 files.

"""
import os
import re
import sys
import logging
import argparse

from email.utils import formatdate
from urllib.parse import quote
from xml.sax.saxutils import escape
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURATION
BASE_URL = "https://pod.afm.co/Bhikku_Samahita/DhammaOnAir/"
PODCAST_TITLE = "Dhamma on Air"
AUTHOR = "Bikkhu Samahita"
DESCRIPTION = "A collection of Buddhist-themed audio episodes."
COVER_IMAGE = "https://www.antoniomagni.com/what-buddha-said/assets/images/samahita.jpg"

def generate_rss_header(base_url, cover_image):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>{PODCAST_TITLE}</title>
    <link>{base_url}</link>
    <description>{DESCRIPTION}</description>
    <language>en-us</language>
    <itunes:author>{AUTHOR}</itunes:author>
    <itunes:image href="{cover_image}"/>
    <itunes:summary>{DESCRIPTION}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <image>
      <url>{cover_image}</url>
      <title>{PODCAST_TITLE}</title>
      <link>{base_url}</link>
    </image>
"""

def generate_rss_footer():
    return "  </channel>\n</rss>\n"

def generate_episode_item(
    ep_num, title_raw, description, base_url, encoded_filename, file_size,
    pub_date, itunes_image_url, explicit, duration=None
):
    title = escape(f"Episode {ep_num}: {title_raw}")
    description = escape(description)
    # media:thumbnail and media:content for artwork and audio
    media_thumbnail = f'<media:thumbnail url="{itunes_image_url}"/>'
    media_content = (
        f'<media:content url="{base_url}{encoded_filename}" type="audio/mpeg" fileSize="{file_size}" medium="audio"/>'
    )
    # media:title and media:description
    media_title = f'<media:title>{title}</media:title>'
    media_description = f'<media:description>{description}</media:description>'
    # itunes:duration if available
    itunes_duration = f"<itunes:duration>{duration}</itunes:duration>" if duration else ""
    return f"""
    <item>
      <title>{title}</title>
      <description>{description}</description>
      <enclosure url="{base_url}{encoded_filename}" length="{file_size}" type="audio/mpeg"/>
      <guid>{base_url}{encoded_filename}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:image href="{itunes_image_url}"/>
      <itunes:explicit>{explicit}</itunes:explicit>
      {itunes_duration}
      {media_thumbnail}
      {media_content}
      {media_title}
      {media_description}
    </item>
"""

def get_mp3_duration(filepath):
    try:
        audio = MP3(filepath)
        seconds = int(audio.info.length)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02}:{s:02}"
        else:
            return f"{m}:{s:02}"
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Generate a podcast RSS feed from a directory of MP3 files."
    )
    parser.add_argument(
        "audio_dir",
        help="Directory containing MP3 files."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output RSS XML filename. If not specified, prints to stdout.",
        default=None
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for enclosure links (default: %(default)s)",
        default=BASE_URL
    )
    parser.add_argument(
        "--cover-image",
        help="Default podcast cover image URL (default: %(default)s)",
        default=COVER_IMAGE
    )
    parser.add_argument(
        "--artwork-dir",
        help="Subdirectory for episode artwork (default: episode_artwork under audio_dir)",
        default=None
    )
    args = parser.parse_args()

    audio_dir = args.audio_dir
    base_url = args.base_url if args.base_url.endswith('/') else args.base_url + '/'
    cover_image = args.cover_image
    episode_artwork_dir = args.artwork_dir or os.path.join(audio_dir, "episode_artwork")
    episode_artwork_url = "/assets/images/episode_artwork/"

    # List all .mp3 files in the directory
    try:
        all_files = os.listdir(audio_dir)
    except FileNotFoundError:
        logger.error(f"❌ Directory not found: {audio_dir}")
        sys.exit(1)

    mp3_files = [f for f in all_files if f.lower().endswith(".mp3")]
    if not mp3_files:
        logger.error("❌ No MP3 files found in the directory.")
        sys.exit(1)

    # Sort by episode number extracted from filename prefix
    def extract_episode_number(filename):
        match = re.match(r"(\d+)", filename)
        return int(match.group(1)) if match else 9999  # fallback if no number

    mp3_files.sort(key=extract_episode_number)

    # Ensure episode artwork directory exists
    os.makedirs(episode_artwork_dir, exist_ok=True)

    rss_feed = generate_rss_header(base_url, cover_image)
    for filename in mp3_files:
        ep_match = re.match(r"(\d+)\s+(.*)\.mp3", filename)
        if not ep_match:
            logger.warning(f"⚠️ Skipping file (no episode number prefix): {filename}")
            continue

        ep_num = ep_match.group(1)
        title_raw = ep_match.group(2).strip()
        description = title_raw
        full_path = os.path.join(audio_dir, filename)

        # --- Extract episode artwork ---
        episode_artwork_filename = f"cover-{ep_num}.jpg"
        episode_artwork_path = os.path.join(episode_artwork_dir, episode_artwork_filename)
        episode_artwork_url_full = episode_artwork_url + episode_artwork_filename
        has_episode_artwork = False

        try:
            audio = MP3(full_path, ID3=ID3)
            if audio.tags is not None:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        # Save artwork if not already saved
                        if not os.path.exists(episode_artwork_path):
                            with open(episode_artwork_path, "wb") as img:
                                img.write(tag.data)
                        has_episode_artwork = True
                        break
        except Exception as e:
            logger.warning(f"⚠️ Could not extract artwork from {filename}: {e}")

        try:
            file_size = os.path.getsize(full_path)
            # Get file creation time (birth time on macOS, ctime on other systems)
            try:
                file_creation_time = os.stat(full_path).st_birthtime
            except AttributeError:
                # Fallback to ctime if birthtime is not available
                file_creation_time = os.stat(full_path).st_ctime
        except FileNotFoundError:
            logger.error(f"⚠️ File not found: {full_path}")
            file_size = 0
            file_creation_time = None

        # Use file creation time for publication date, fallback to current time if unavailable
        if file_creation_time:
            pub_date = formatdate(timeval=file_creation_time, localtime=False, usegmt=True)
        else:
            pub_date = formatdate(timeval=None, localtime=False, usegmt=True)
        
        encoded_filename = quote(filename)
        itunes_image_url = episode_artwork_url_full if has_episode_artwork else cover_image
        duration = get_mp3_duration(full_path)
        explicit = "false"

        rss_feed += generate_episode_item(
            ep_num, title_raw, description, base_url, encoded_filename, file_size,
            pub_date, itunes_image_url, explicit, duration
        )

    rss_feed += generate_rss_footer()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rss_feed)
        logger.info(f"✅ RSS feed written to: {args.output}")
    else:
        print(rss_feed)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a podcast RSS feed from a directory of MP3 files."
    )
    parser.add_argument(
        "audio_dir",
        help="Directory containing MP3 files."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output RSS XML filename. If not specified, prints to stdout.",
        default=None
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for enclosure links (default: %(default)s)",
        default=BASE_URL
    )
    parser.add_argument(
        "--cover-image",
        help="Default podcast cover image URL (default: %(default)s)",
        default=COVER_IMAGE
    )
    parser.add_argument(
        "--artwork-dir",
        help="Subdirectory for episode artwork (default: episode_artwork under audio_dir)",
        default=None
    )
    return parser.parse_args()

if __name__ == "__main__":
    main()
