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