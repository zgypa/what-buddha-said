# Tool used to generate the podcast feed

This is what i did:

1. Downloaded the entire mp3 collection
2. Ran the script like this

```bash
./podcast_rss_feed_generator.py --artwork-dir ../podcasts/dhamma_on_air/episode_artwork --output ../podcasts/dhamma_on_air/feed.xml ~/Downloads/Bhikku_Samahita/DhammaOnAir
```

3. Uploaded to media server with rsync, replacing pod.afmco with the actual server

```bash
rsync -av ~/src/afm/what-buddha-said/podcasts/dhamma_on_air/ pod.afm.co:/webdav/podcasts/Bhikku_Samahita/DhammaOnAir/
```

4. Commit to github
5. Feed can now be reached from https://www.antoniomagni.com/what-buddha-said/podcasts/dhamma_on_air/feed.xml  and https://pod.afm.co/Bhikku_Samahita/DhammaOnAir/feed.xml.
6. Easier to subscribe to the github feed, because then i can change without having to deploy to see changes.

## Episode Summaries

Each episode in the podcast feed can have a summary that is shown in podcast apps. Summaries are loaded automatically by the feed generator from the following location:

```
../podcasts/dhamma_on_air/summaries/summary-XXX.txt
```

where `XXX` is the zero-padded episode number (e.g. `summary-069.txt` for episode 69).

**How to create a summary:**
- Get the transcript for the episode (for example, using [restream.io](https://restream.io) or another transcription tool).
- Use a summarization tool (like Gemini or similar) to generate a concise summary.
- Format the summary as short bullet points, grouped by the main sections of the episode, so listeners can quickly scan and decide if they want to listen.
- Example structure for the summary:
  - reading
  - update on meditation hall
  - the simile
  - question 1
  - question 2
  - question 3
  - closing reading

**Example summary file path:**
```
../podcasts/dhamma_on_air/summaries/summary-069.txt
```

If a summary file does not exist for an episode, the feed will show a default header only.

## Transcripts

If you want to store full transcripts for episodes, use the following folder and filename schema:

```
./podcasts/transcripts/transcript-XXX.txt
```

where `XXX` is the zero-padded episode number (e.g. `transcript-069.txt` for episode 69).