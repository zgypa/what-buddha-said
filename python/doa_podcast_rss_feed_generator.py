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
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import xml.dom.minidom

from email.utils import formatdate
from urllib.parse import quote
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from PIL import Image, ImageOps
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURATION
MEDIA_BASE_URL = "https://pod.afm.co/Bhikku_Samahita/DhammaOnAir"
FEED_BASE_URL = "https://www.antoniomagni.com/what-buddha-said"
PODCAST_TITLE = "Dhamma on Air"
AUTHOR = "Samahita Thera"
DESCRIPTION = "A collection of Buddhist-themed audio episodes."
COVER_IMAGE = f"{FEED_BASE_URL}/assets/images/samahita_cartoon.jpg"
EPISODE_ARTWORK_URL = f"{MEDIA_BASE_URL}/episode_artwork/"
# Size for episode artwork in pixels. Apple Podcasts requires at least 1400x1400, but recommends 3000x3000 for best quality.
ARTWORK_SIZE = 3000
SUMMARIES_DIR = os.path.join(os.path.dirname(
    __file__), "..", "podcasts", "dhamma_on_air", "summaries")


# Fixed episode dates (episode number: YYYY-MM-DD)
FIXED_EPISODE_DATES = {
    3:  "2015-12-12",
    22: "2016-05-15",
    25: "2016-06-17",
    45: "2016-11-19",
    54: "2017-01-19",
    68: "2017-07-07",
    98: "2018-04-15",
}

PODCAST_CATEGORIES = [
    ("Religion & Spirituality", "Buddhism"),
    # Add more categories/subcategories as needed
]
COPYRIGHT = "No Copyright. Free to share and use."
OWNER_NAME = "Toni Magni"
# Change to a real email if desired
OWNER_EMAIL = "what-buddha-said-net@antoniomagni.com"


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
        today = datetime.now(timezone.utc)
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
            result[ep] = datetime.now(timezone.utc)
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Generate podcast RSS feed.")
    parser.add_argument("audio_dir", help="Directory containing MP3 files.")
    parser.add_argument("--base-url", default=MEDIA_BASE_URL,
                        help="Base URL for media files.")
    parser.add_argument("--cover-image", default=COVER_IMAGE,
                        help="Podcast cover image URL.")
    parser.add_argument("--artwork-dir", help="Directory for episode artwork.")
    parser.add_argument("--overwrite-artwork", action="store_true",
                        help="Overwrite existing episode artwork PNG files.")
    parser.add_argument(
        "--output", help="Path to output XML file (default: feed.xml in audio_dir)")
    return parser.parse_args()


def list_mp3_files(audio_dir):
    try:
        all_files = os.listdir(audio_dir)
    except FileNotFoundError:
        logger.error(f"❌ Directory not found: {audio_dir}")
        sys.exit(1)
    mp3_files = [f for f in all_files if f.lower().endswith(".mp3")]
    if not mp3_files:
        logger.error("❌ No MP3 files found in the directory.")
        sys.exit(1)
    return mp3_files


def ensure_dir_exists(directory):
    os.makedirs(directory, exist_ok=True)


def build_episode_infos(mp3_files, audio_dir):
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

    return episode_infos


def load_episode_summary(episode_number: int, title: str, summaries_dir: str) -> str:
    """
    Load episode summary from ../podcasts/dhamma_on_air/summaries/summary-XXX.txt
    where XXX is the zero-padded episode number.

    Args:
        episode_number (int): The episode number
        audio_dir (str): The audio directory path

    Returns:
        str: The complete description text for the RSS feed
    """
    # Default header for all episodes
    header = f"DoA #{episode_number}: {title}\nArtist: {AUTHOR}\n{PODCAST_TITLE}"

    # Construct path to summary file
    summary_dir = summaries_dir or SUMMARIES_DIR
    summary_file = os.path.join(
        summary_dir, f"summary-{episode_number:03d}.txt")

    # Try to load the summary file
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_content = f.read().strip()
            if summary_content:
                return f"{header}\n\n{summary_content}"
        except Exception as e:
            logger.warning(f"Failed to read summary file {summary_file}: {e}")
    else:
        logger.warning(f"Summary file not found: {summary_file}")
    # Return just the header if no summary exists or if there was an error
    return header


def generate_rss_feed(base_url, cover_image, episode_infos, audio_dir, episode_artwork_dir, ep_dates, overwrite_artwork):
    rss = ET.Element('rss', {
        'version': '2.0',
        'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'xmlns:media': 'http://search.yahoo.com/mrss/'
    })
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = PODCAST_TITLE
    ET.SubElement(channel, 'link').text = FEED_BASE_URL
    ET.SubElement(channel, 'description').text = DESCRIPTION
    ET.SubElement(channel, 'language').text = 'en-us'
    ET.SubElement(channel, 'itunes:author').text = AUTHOR
    ET.SubElement(channel, 'itunes:image', {'href': cover_image})
    ET.SubElement(channel, 'itunes:summary').text = DESCRIPTION
    ET.SubElement(channel, 'itunes:explicit').text = 'false'
    ET.SubElement(channel, 'itunes:type').text = 'episodic'
    ET.SubElement(channel, 'copyright').text = COPYRIGHT

    owner = ET.SubElement(channel, 'itunes:owner')
    ET.SubElement(owner, 'itunes:name').text = OWNER_NAME
    ET.SubElement(owner, 'itunes:email').text = OWNER_EMAIL

    # Categories
    for cat, subcat in PODCAST_CATEGORIES:
        if subcat:
            cat_el = ET.SubElement(channel, 'itunes:category', {'text': cat})
            ET.SubElement(cat_el, 'itunes:category', {'text': subcat})
        else:
            ET.SubElement(channel, 'itunes:category', {'text': cat})
        ET.SubElement(channel, 'category').text = cat

    image = ET.SubElement(channel, 'image')
    ET.SubElement(image, 'url').text = cover_image
    ET.SubElement(image, 'title').text = PODCAST_TITLE
    ET.SubElement(image, 'link').text = FEED_BASE_URL

    # Add episodes as <item>
    for ep_num_int, id3_title, filename in tqdm(episode_infos, desc="Processing episodes"):
        description = ""
        ep_num = str(ep_num_int).zfill(2)
        full_path = os.path.join(audio_dir, filename)

        # Use ID3 title if available, else fallback to filename (without extension)
        title_raw = id3_title if id3_title else os.path.splitext(filename)[0]

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
                        # Convert and pad to ARTWORK_SIZExARTWORK_SIZE JPEG with max compression
                        if overwrite_artwork or not os.path.exists(episode_artwork_path):
                            img = Image.open(BytesIO(tag.data)).convert("RGB")
                            img_padded = ImageOps.pad(
                                img, (ARTWORK_SIZE, ARTWORK_SIZE), color=(0, 0, 0), centering=(0.5, 0.5))
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

        # Load episode description with summary
        description += load_episode_summary(
            ep_num_int, title=title_raw, summaries_dir=SUMMARIES_DIR)

        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = f"DoA #{ep_num}: {title_raw}"
        ET.SubElement(item, 'link').text = FEED_BASE_URL
        ET.SubElement(item, 'description').text = description
        enclosure = ET.SubElement(item, 'enclosure', {
            'url': f"{base_url}{encoded_filename}",
            'length': str(file_size),
            'type': "audio/mpeg"
        })
        ET.SubElement(item, 'guid').text = f"{base_url}{encoded_filename}"
        ET.SubElement(item, 'pubDate').text = pub_date
        ET.SubElement(item, 'itunes:image', {'href': itunes_image_url})
        ET.SubElement(item, 'itunes:explicit').text = explicit
        if duration:
            ET.SubElement(item, 'itunes:duration').text = duration
        # Keep this commented out for now, trying to remove media tags to see if this resolves issues with Apple Podcast not loading artwork of episode
        # media_thumbnail = ET.SubElement(item, 'media:thumbnail', {
        #     'url': itunes_image_url
        # })
        # media_content = ET.SubElement(item, 'media:content', {
        #     'url': f"{base_url}{encoded_filename}",
        #     'type': "audio/mpeg",
        #     'fileSize': str(file_size),
        #     'medium': "audio"
        # })
        # media_title = ET.SubElement(item, 'media:title')
        # media_title.text = f"Episode {ep_num}: {title_raw}"
        # media_description = ET.SubElement(item, 'media:description')
        # media_description.text = description

    # Return pretty-printed XML string
    rss_feed = ET.tostring(rss, encoding='unicode', method='xml')

    return rss_feed


def write_feed(feed_xml, output_path):
    # Pretty-print XML before saving
    parsed = xml.dom.minidom.parseString(feed_xml)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    with open(output_path, "wb") as f:
        f.write(pretty_xml)


def main():
    args = parse_args()
    audio_dir = args.audio_dir
    base_url = args.base_url if args.base_url.endswith(
        '/') else args.base_url + '/'
    cover_image = args.cover_image
    episode_artwork_dir = args.artwork_dir or os.path.join(
        audio_dir, "episode_artwork")
    ensure_dir_exists(episode_artwork_dir)

    mp3_files = list_mp3_files(audio_dir)
    episode_infos = build_episode_infos(mp3_files, audio_dir)
    ep_dates = interpolate_dates([ep_info[0] for ep_info in episode_infos])
    feed_xml = generate_rss_feed(
        base_url, cover_image, episode_infos, audio_dir, episode_artwork_dir, ep_dates, args.overwrite_artwork
    )
    output_path = args.output if args.output else os.path.join(
        audio_dir, "feed.xml")
    write_feed(feed_xml, output_path)
    logger.info(f"✅ RSS feed generated at {output_path}")


if __name__ == "__main__":
    main()
