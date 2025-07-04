#!/usr/bin/env python3
import os
import re
import sys
from email.utils import formatdate
from urllib.parse import quote
from xml.sax.saxutils import escape
import logging
# Add mutagen for ID3 extraction
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
EPISODE_ARTWORK_DIR = os.path.join(AUDIO_DIR, "episode_artwork")
EPISODE_ARTWORK_URL = BASE_URL + "episode_artwork/"

# Get directory from command-line
if len(sys.argv) < 2:
    logger.error("❌ Please provide the directory path containing MP3 files.")
    logger.info("Usage: python generate_podcast_rss.py /path/to/mp3s")
    sys.exit(1)

AUDIO_DIR = sys.argv[1]

# List all .mp3 files in the directory
try:
    all_files = os.listdir(AUDIO_DIR)
except FileNotFoundError:
    logger.error(f"❌ Directory not found: {AUDIO_DIR}")
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
os.makedirs(EPISODE_ARTWORK_DIR, exist_ok=True)

rss_items = []
for filename in mp3_files:
    ep_match = re.match(r"(\d+)\s+(.*)\.mp3", filename)
    if not ep_match:
        logger.warning(f"⚠️ Skipping file (no episode number prefix): {filename}")
        continue

    ep_num = ep_match.group(1)
    title_raw = ep_match.group(2).strip()
    title = escape(f"Episode {ep_num}: {title_raw}")
    description = escape(title_raw)
    full_path = os.path.join(AUDIO_DIR, filename)

    # --- Extract episode artwork ---
    episode_artwork_filename = f"cover-{ep_num}.jpg"
    episode_artwork_path = os.path.join(EPISODE_ARTWORK_DIR, episode_artwork_filename)
    episode_artwork_url = EPISODE_ARTWORK_URL + episode_artwork_filename
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

    # --- Add episode artwork to item ---
    itunes_image_tag = f'<itunes:image href="{episode_artwork_url if has_episode_artwork else COVER_IMAGE}"/>'

    rss_items.append(f"""
    <item>
      <title>{title}</title>
      <description>{description}</description>
      <enclosure url="{BASE_URL}{encoded_filename}" length="{file_size}" type="audio/mpeg"/>
      <guid>{BASE_URL}{encoded_filename}</guid>
      <pubDate>{pub_date}</pubDate>
      {itunes_image_tag}
    </item>
""")

rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{PODCAST_TITLE}</title>
    <link>{BASE_URL}</link>
    <description>{DESCRIPTION}</description>
    <language>en-us</language>
    <itunes:author>{AUTHOR}</itunes:author>
    <itunes:image href="{COVER_IMAGE}"/>
    <itunes:summary>{DESCRIPTION}</itunes:summary>
    {''.join(rss_items)}
  </channel>
</rss>
"""

print(rss_feed)

# Write RSS XML to file
# output_file = "podcast_feed.xml"
# with open(output_file, "w", encoding="utf-8") as f:
#     f.write(rss_feed)

# print(f"✅ RSS feed written to: {output_file}")
