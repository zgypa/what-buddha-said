import xml.etree.ElementTree as ET
from email.utils import formatdate
from datetime import datetime

# --- CONFIGURATION ---

PODCAST_TITLE = "Sutta Discourses"
PODCAST_LINK = "https://store.pariyatti.org/sutta-discourses-by-s-n-goenka-streaming-audio-vipassana"
PODCAST_DESCRIPTION = """In this series of discourses S.N. Goenka discusses the following suttas:

    Anapana Sati Sutta
    Anatta Lakkhana Sutta
    Dhammacakka Pavattana Sutta
    Girimananda Sutta
    Vedana Samyuttam - Datthabba Sutta & Salla Sutta
    Vedana Samyuttam - Samadhi Sutta, Sukha Sutta & Pahana Sutta
"""
PODCAST_LANGUAGE = "en-us"
PODCAST_AUTHOR = "S.N. Goenka"
PODCAST_IMAGE = "https://store.pariyatti.org/thumbnail.asp?file=/assets/images/StreamDisc_Audio_SNG.jpg&maxx=300&maxy=0"
PODCAST_COPYRIGHT = "Copyright 2024 Jane Doe"
PODCAST_OWNER_NAME = "Pariyatti"
PODCAST_OWNER_EMAIL = "jane@example.com"
PODCAST_EXPLICIT = "false"

# Episodes: key = episode number or id, value = dict with info
EPISODES = {
    1: {
        "title": "Discourse on Anapana Sati Sutta",
        "description": "Discourse on Anapana Sati Sutta",
        "audio_url": "https://discourses.dhamma.org/oml/recordings/uuid/5f9f8573-ffee-4831-bb82-c92df3b9502f.mp3",
        "audio_length": "12345678",
        "pub_date": "2024-06-01T12:00:00",
        "image": PODCAST_IMAGE,
        "duration": "12:34"
    },
    2: {
        "title": "Episode 2: Deep Dive",
        "description": "A deeper look at the topic.",
        "audio_url": "https://discourses.dhamma.org/oml/recordings/uuid/1eca83eb-8460-4fb1-94a8-f6c6a82d0f9d.mp3",
        "audio_length": "23456789",
        "pub_date": "2024-06-08T12:00:00",
        "image": "https://example.com/audio/ep2.jpg",
        "duration": "15:00"
    },
}

# --- RSS GENERATION ---

def make_rss():
    rss = ET.Element('rss', {
        'version': '2.0',
        'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'
    })
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = PODCAST_TITLE
    ET.SubElement(channel, 'link').text = PODCAST_LINK
    ET.SubElement(channel, 'description').text = PODCAST_DESCRIPTION
    ET.SubElement(channel, 'language').text = PODCAST_LANGUAGE
    ET.SubElement(channel, 'itunes:author').text = PODCAST_AUTHOR
    ET.SubElement(channel, 'itunes:image', {'href': PODCAST_IMAGE})
    ET.SubElement(channel, 'copyright').text = PODCAST_COPYRIGHT
    ET.SubElement(channel, 'itunes:explicit').text = PODCAST_EXPLICIT

    owner = ET.SubElement(channel, 'itunes:owner')
    ET.SubElement(owner, 'itunes:name').text = PODCAST_OWNER_NAME
    ET.SubElement(owner, 'itunes:email').text = PODCAST_OWNER_EMAIL

    # Add episodes
    for ep in sorted(EPISODES.keys()):
        info = EPISODES[ep]
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = info["title"]
        ET.SubElement(item, 'description').text = info["description"]
        ET.SubElement(item, 'pubDate').text = formatdate(
            timeval=datetime.fromisoformat(info["pub_date"]).timestamp(),
            localtime=False, usegmt=True
        )
        ET.SubElement(item, 'enclosure', {
            'url': info["audio_url"],
            'length': info["audio_length"],
            'type': "audio/mpeg"
        })
        ET.SubElement(item, 'guid').text = info["audio_url"]
        ET.SubElement(item, 'itunes:image', {'href': info.get("image", PODCAST_IMAGE)})
        ET.SubElement(item, 'itunes:explicit').text = PODCAST_EXPLICIT
        if "duration" in info:
            ET.SubElement(item, 'itunes:duration').text = info["duration"]

    return ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")

if __name__ == "__main__":
    xml = make_rss()
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    print("Feed written to feed.xml")
