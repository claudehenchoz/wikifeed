import json
import re
import urllib.request
import xml.dom.minidom
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def add_rss_item(channel, title, link, description, timestamp_str, now_utc):
    """Helper to consistently format and append items to the RSS feed."""
    item_el = SubElement(channel, "item")
    SubElement(item_el, "title").text = title
    SubElement(item_el, "link").text = link
    SubElement(item_el, "description").text = description
    SubElement(item_el, "guid").text = link

    # Parse the provided timestamp, fallback to current time if parsing fails
    if timestamp_str:
        try:
            mod_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            pub_date_str = format_datetime(mod_time)
        except ValueError:
            pub_date_str = format_datetime(now_utc)
    else:
        pub_date_str = format_datetime(now_utc)

    SubElement(item_el, "pubDate").text = pub_date_str


def generate_rss():
    now = datetime.now(timezone.utc)
    data = None

    # The REST API generates daily feeds. If it's early in the UTC day and today's
    # feed isn't published yet, fallback to yesterday's data.
    for offset in range(3):
        target_date = now - timedelta(days=offset)
        date_str = target_date.strftime("%Y/%m/%d")
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{date_str}"

        req = urllib.request.Request(
            url, headers={"User-Agent": "Wikipedia-Daily-RSS-Bot/1.0 (github-actions)"}
        )
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                break  # Successfully fetched
        except Exception:
            continue

    if not data:
        print("Error: Could not retrieve featured data from Wikipedia.")
        return

    # Initialize RSS XML Structure
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "Wikipedia - Daily Features & News"
    SubElement(channel, "link").text = "https://en.wikipedia.org/wiki/Main_Page"
    SubElement(
        channel, "description"
    ).text = "Wikipedia's In The News, Featured Article, and Top 10 Most Read."
    SubElement(channel, "pubDate").text = format_datetime(now)

    # 1. Today's Featured Article (TFA)
    tfa = data.get("tfa")
    if tfa:
        title = f"[Featured Article] {tfa.get('normalizedtitle', tfa.get('title', ''))}"
        link = tfa.get("content_urls", {}).get("desktop", {}).get("page", "")
        desc = tfa.get("extract", "Today's featured article.")
        ts = tfa.get("timestamp")
        add_rss_item(channel, title, link, desc, ts, now)

    # 2. In The News
    for item in data.get("news", []):
        links = item.get("links", [])
        if not links:
            continue

        main_article = links[0]
        story_html = item.get("story", "")
        plain_story = re.sub(r"<[^>]+>", "", story_html)  # Strip HTML

        title = f"[In the News] {plain_story}"
        link = main_article.get("content_urls", {}).get("desktop", {}).get("page", "")
        desc = main_article.get("extract", plain_story)
        ts = main_article.get("timestamp")

        add_rss_item(channel, title, link, desc, ts, now)

    # 3. Top 10 Most Read Articles
    most_read_articles = data.get("mostread", {}).get("articles", [])[:10]
    for idx, article in enumerate(most_read_articles, start=1):
        clean_title = article.get("normalizedtitle", article.get("title", ""))
        title = f"[Most Read #{idx}] {clean_title}"
        link = article.get("content_urls", {}).get("desktop", {}).get("page", "")

        views = article.get("views", 0)
        base_desc = article.get("extract", "No description available.")
        desc = f"Daily Views: {views:,} — {base_desc}"
        ts = article.get("timestamp")

        add_rss_item(channel, title, link, desc, ts, now)

    # Pretty-print and save to disk
    xml_str = xml.dom.minidom.parseString(tostring(rss)).toprettyxml(indent="  ")
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)


if __name__ == "__main__":
    generate_rss()
