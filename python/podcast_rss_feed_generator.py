#!/usr/bin/env python3
"""
Generate the RSS feed from a directory of MP3 files.

"""
import os
import re
import sys
import logging
import argparse
from io import BytesIO
from datetime import datetime, timedelta

from email.utils import formatdate
from urllib.parse import quote
from xml.sax.saxutils import escape
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from PIL import Image, ImageOps
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURATION
MEDIA_BASE_URL = "https://pod.afm.co/Bhikku_Samahita/DhammaOnAir/"
FEED_BASE_URL = "https://www.antoniomagni.com/what-buddha-said"
PODCAST_TITLE = "Dhamma on Air"
AUTHOR = "Bikkhu Samahita"
DESCRIPTION = "A collection of Buddhist-themed audio episodes."
COVER_IMAGE = f"{FEED_BASE_URL}/assets/images/samahita_cartoon.jpg"
EPISODE_ARTWORK_URL = f"{FEED_BASE_URL}/podcasts/dhamma_on_air/episode_artwork/"

# Fixed episode dates (episode number: YYYY-MM-DD)
FIXED_EPISODE_DATES = {
    3:  "2015-12-12",
    22: "2016-05-15",
    25: "2016-06-17",
    45: "2016-11-19",
    54: "2017-01-19",
    98: "2018-04-15",
}

PODCAST_CATEGORIES = [
    ("Religion & Spirituality", "Buddhism"),
    # Add more categories/subcategories as needed
]
COPYRIGHT = "No Copyright. Free to share and use."
OWNER_NAME = "Bikkhu Samahita"
OWNER_EMAIL = "what-buddha-said-net@antoniomagni.com"  # Change to a real email if desired


def generate_rss_header(base_url, cover_image):
    # Build category tags
    itunes_category_tags = ""
    for cat, subcat in PODCAST_CATEGORIES:
        cat_escaped = cat.replace("&", "&amp;")
        subcat_escaped = subcat.replace("&", "&amp;") if subcat else None
        if subcat:
            itunes_category_tags += f'    <itunes:category text="{cat_escaped}">\n      <itunes:category text="{subcat_escaped}"/>\n    </itunes:category>\n'
        else:
            itunes_category_tags += f'    <itunes:category text="{cat_escaped}"/>\n'
    # Add generic <category> for RSS readers
    rss_category_tags = "".join(
        [f'    <category>{cat.replace("&", "&amp;")}</category>\n' for cat, _ in PODCAST_CATEGORIES])

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
    <itunes:type>episodic</itunes:type>
    <copyright>{COPYRIGHT}</copyright>
    <itunes:owner>
      <itunes:name>{OWNER_NAME}</itunes:name>
      <itunes:email>{OWNER_EMAIL}</itunes:email>
    </itunes:owner>
{itunes_category_tags}{rss_category_tags}    <image>
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
    # Build episode web page URL (fallback to audio file if no web page)
    # You can customize this to point to a real episode page if available
    episode_page_url = f"{base_url}{encoded_filename}"
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
      <link>{episode_page_url}</link>
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


def extract_id3_description(audio):
    """Extract a detailed description from all available ID3 tags."""
    lines = []
    # Title
    title = audio.tags.get('TIT2')
    if title:
        lines.append(f"Title: {title.text[0]}")
    # Artist
    artist = audio.tags.get('TPE1')
    if artist:
        lines.append(f"Artist: {artist.text[0]}")
    # Album
    album = audio.tags.get('TALB')
    if album:
        lines.append(f"Album: {album.text[0]}")
    # Genre
    genre = audio.tags.get('TCON')
    if genre:
        lines.append(f"Genre: {genre.text[0]}")
    # Year/Date
    date = audio.tags.get('TDRC')
    if date:
        lines.append(f"Date: {date.text[0]}")
    # Comments
    for comm in audio.tags.getall('COMM'):
        if comm.text:
            lines.append(f"Comment: {comm.text[0]}")
    # Lyrics
    for uslt in audio.tags.getall('USLT'):
        if uslt.text:
            lines.append(f"Lyrics: {uslt.text}")
    # Custom TXXX frames
    for txxx in audio.tags.getall('TXXX'):
        if txxx.desc and txxx.text:
            lines.append(f"{txxx.desc}: {txxx.text[0]}")
    # Join all lines
    return "\n".join(lines) if lines else None


def extract_id3_title_and_track(audio):
    """Extract title and track number from ID3 tags."""
    title = None
    track = None
    if audio.tags:
        tit2 = audio.tags.get('TIT2')
        if tit2 and tit2.text:
            title = tit2.text[0]
        trck = audio.tags.get('TRCK')
        if trck and trck.text:
            # Track number may be '5/12', just take the first part
            track = str(trck.text[0]).split('/')[0]
    return title, track


def parse_fixed_dates():
    # Convert to {ep_num: datetime}
    return {ep: datetime.strptime(date, "%Y-%m-%d") for ep, date in FIXED_EPISODE_DATES.items()}


def interpolate_dates(episode_numbers):
    """
    Given a sorted list of episode numbers, return a dict {ep_num: datetime}
    using fixed dates and linear interpolation.
    """
    fixed = parse_fixed_dates()
    result = {}
    sorted_eps = sorted(episode_numbers)
    # Prepare list of (ep_num, date) sorted by ep_num
    fixed_points = sorted(fixed.items())
    # If no fixed points, fallback to today
    if not fixed_points:
        today = datetime.utcnow()
        for ep in sorted_eps:
            result[ep] = today
        return result

    # For each episode, find its date
    for idx, ep in enumerate(sorted_eps):
        # If fixed, use it
        if ep in fixed:
            result[ep] = fixed[ep]
            continue
        # Find previous and next fixed points
        prev = None
        next_ = None
        for f_ep, f_date in fixed_points:
            if f_ep < ep:
                prev = (f_ep, f_date)
            elif f_ep > ep and next_ is None:
                next_ = (f_ep, f_date)
        if prev and next_:
            # Interpolate
            ep_span = next_[0] - prev[0]
            day_span = (next_[1] - prev[1]).days
            if ep_span == 0 or day_span == 0:
                interp_date = prev[1]
            else:
                days_per_ep = day_span / ep_span
                interp_date = prev[1] + \
                    timedelta(days=(ep - prev[0]) * days_per_ep)
            result[ep] = interp_date
        elif prev and not next_:
            # Extrapolate forward
            # Use last two fixed points if possible
            prev2 = None
            for f_ep, f_date in reversed(fixed_points):
                if f_ep < prev[0]:
                    prev2 = (f_ep, f_date)
                    break
            if prev2:
                ep_span = prev[0] - prev2[0]
                day_span = (prev[1] - prev2[1]).days
                days_per_ep = day_span / ep_span if ep_span else 7
            else:
                days_per_ep = 7  # fallback
            interp_date = prev[1] + \
                timedelta(days=(ep - prev[0]) * days_per_ep)
            result[ep] = interp_date
        elif next_ and not prev:
            # Extrapolate backward
            # Use first two fixed points if possible
            next2 = None
            for f_ep, f_date in fixed_points:
                if f_ep > next_[0]:
                    next2 = (f_ep, f_date)
                    break
            if next2:
                ep_span = next2[0] - next_[0]
                day_span = (next2[1] - next_[1]).days
                days_per_ep = day_span / ep_span if ep_span else 7
            else:
                days_per_ep = 7  # fallback
            interp_date = next_[1] - \
                timedelta(days=(next_[0] - ep) * days_per_ep)
            result[ep] = interp_date
        else:
            # Should not happen, fallback to today
            result[ep] = datetime.utcnow()
    return result


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
        default=MEDIA_BASE_URL
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
    parser.add_argument(
        "--overwrite-artwork",
        action="store_true",
        help="Overwrite existing episode artwork PNG files."
    )
    args = parser.parse_args()

    audio_dir = args.audio_dir
    base_url = args.base_url if args.base_url.endswith(
        '/') else args.base_url + '/'
    cover_image = args.cover_image
    episode_artwork_dir = args.artwork_dir or os.path.join(
        audio_dir, "episode_artwork")

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

    # Ensure episode artwork directory exists
    os.makedirs(episode_artwork_dir, exist_ok=True)

    # Build a list of tuples: (track_number, title, filename)
    episode_infos = []
    for filename in mp3_files:
        full_path = os.path.join(audio_dir, filename)
        try:
            audio = MP3(full_path, ID3=ID3)
            id3_title, id3_track = extract_id3_title_and_track(audio)
            # Only use files with a valid track number
            if id3_track and id3_track.isdigit():
                episode_infos.append((int(id3_track), id3_title, filename))
            else:
                # fallback: try to extract from filename
                ep_match = re.match(r"(\d+)", filename)
                if ep_match:
                    episode_infos.append(
                        (int(ep_match.group(1)), id3_title, filename))
        except Exception as e:
            logger.warning(
                f"⚠️ Could not extract ID3 tags from {filename}: {e}")
            ep_match = re.match(r"(\d+)", filename)
            if ep_match:
                episode_infos.append((int(ep_match.group(1)), None, filename))

    # Sort by episode number (track)
    episode_infos.sort(key=lambda x: x[0])

    # Interpolate pubDates
    episode_numbers = [ep[0] for ep in episode_infos]
    ep_dates = interpolate_dates(episode_numbers)

    rss_feed = generate_rss_header(base_url, cover_image)
    for ep_num_int, id3_title, filename in tqdm(episode_infos, desc="Processing episodes"):
        ep_num = str(ep_num_int).zfill(2)
        full_path = os.path.join(audio_dir, filename)

        # Use ID3 title if available, else fallback to filename (without extension)
        title_raw = id3_title if id3_title else os.path.splitext(filename)[0]

        description = title_raw  # fallback
        has_episode_artwork = False
        episode_artwork_filename = f"cover-{ep_num}.jpg"
        episode_artwork_path = os.path.join(
            episode_artwork_dir, episode_artwork_filename)
        EPISODE_ARTWORK_URL_full = EPISODE_ARTWORK_URL + episode_artwork_filename

        try:
            audio = MP3(full_path, ID3=ID3)
            if audio.tags is not None:
                # Extract artwork
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        # Convert and pad to 1500x1500 JPEG with max compression
                        if args.overwrite_artwork or not os.path.exists(episode_artwork_path):
                            img = Image.open(BytesIO(tag.data)).convert("RGB")
                            img_padded = ImageOps.pad(
                                img, (1500, 1500), color=(0, 0, 0), centering=(0.5, 0.5))
                            img_padded.save(
                                episode_artwork_path,
                                "JPEG",
                                quality=85,  # 85 is usually visually lossless, but you can lower for more compression
                                optimize=True,
                                progressive=True
                            )
                        has_episode_artwork = True
                        break
                # Extract description
                id3_desc = extract_id3_description(audio)
                if id3_desc:
                    description = id3_desc
        except Exception as e:
            logger.warning(
                f"⚠️ Could not extract ID3 tags from {filename}: {e}")

        try:
            file_size = os.path.getsize(full_path)
            try:
                file_creation_time = os.stat(full_path).st_birthtime
            except AttributeError:
                file_creation_time = os.stat(full_path).st_ctime
        except FileNotFoundError:
            logger.error(f"⚠️ File not found: {full_path}")
            file_size = 0
            file_creation_time = None

        # Use interpolated date
        pub_date_dt = ep_dates.get(ep_num_int)
        pub_date = formatdate(timeval=pub_date_dt.timestamp(
        ), localtime=False, usegmt=True) if pub_date_dt else formatdate(timeval=None, localtime=False, usegmt=True)

        encoded_filename = quote(filename)
        itunes_image_url = EPISODE_ARTWORK_URL_full if has_episode_artwork else cover_image
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
        default=MEDIA_BASE_URL
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
