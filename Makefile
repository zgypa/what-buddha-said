.PHONY: serve feed venv

serve:
	bundle exec jekyll serve --baseurl=""

venv:
	if [ ! -d python/.venv ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv python/.venv; \
	fi
	./python/.venv/bin/pip install --upgrade pip --break-system-packages
	./python/.venv/bin/pip install -r python/requirements.txt --break-system-packages

feed: venv
	cd python && . .venv/bin/activate && ./doa_podcast_rss_feed_generator.py --artwork-dir ../podcasts/dhamma_on_air/episode_artwork --output ../podcasts/dhamma_on_air/feed.xml ~/Downloads/Bhikku_Samahita/DhammaOnAir