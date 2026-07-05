import os
import asyncio
from twikit import Client
import random
import time
import requests

# ── File paths ──────────────────────────────────────────────
ACCOUNTS_FILE = "accounts.txt"
TWEETS_FILE   = "tweets.txt"
POSTED_FILE   = "posted.txt"
IMAGES_DIR    = "images"

GRAPHQL_URL = "https://x.com/i/api/graphql/SoVnbfCycZ7fERGCwpZkYA/CreateTweet"
BEARER      = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# ── Helpers ──────────────────────────────────────────────────

def load_accounts():
    accounts = []
    with open(ACCOUNTS_FILE, "r") as f:
        lines = [l.strip() for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i] == "":
            i += 1
            continue
        auth_token = lines[i]
        ct0        = lines[i + 1] if i + 1 < len(lines) else None
        if auth_token and ct0:
            accounts.append({"auth_token": auth_token, "ct0": ct0})
        i += 2
    return accounts


def load_threads():
    threads = []
    with open(TWEETS_FILE, "r") as f:
        content = f.read()
    blocks = content.strip().split("\n---\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        tweets = [t.strip() for t in block.split("\n\n") if t.strip()]
        if tweets:
            threads.append(tweets)
    return threads


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return {}
    posted = {}
    with open(POSTED_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if "|" in line:
                idx, url = line.split("|", 1)
                posted[int(idx)] = url
    return posted


def save_posted(acct_index, tweet_url):
    with open(POSTED_FILE, "a") as f:
        f.write(f"{acct_index}|{tweet_url}\n")


def get_image_path(acct_index):
    for ext in ["jpg", "jpeg", "png", "gif", "webp"]:
        path = os.path.join(IMAGES_DIR, f"{acct_index}.{ext}")
        if os.path.exists(path):
            return path
    return None


def make_session(auth_token, ct0):
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {BEARER}",
        "X-Csrf-Token": ct0,
        "Content-Type": "application/json",
        "Origin": "https://x.com",
        "Referer": "https://x.com/home",
    })
    s.cookies.set("auth_token", auth_token, domain=".x.com")
    s.cookies.set("ct0", ct0, domain=".x.com")
    return s


def upload_image(auth_token, ct0, image_path):
    import asyncio
    from twikit import Client
    ext  = image_path.rsplit(".", 1)[-1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")

    async def _upload():
        client = Client(language="en-US")
        client.set_cookies({"auth_token": auth_token, "ct0": ct0})
        return await client.upload_media(image_path, media_type=mime, wait_for_completion=True)

    return asyncio.run(_upload())


def post_tweet(session, text, reply_to_id=None, media_id=None):
    payload = {
        "variables": {
            "tweet_text": text,
            "dark_request": False,
            "media": {
                "media_entities": [{"media_id": media_id, "tagged_users": []}] if media_id else [],
                "possibly_sensitive": False
            },
            "semantic_annotation_ids": []
        },
        "features": {
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "interactive_text_enabled": True,
            "responsive_web_text_conversations_enabled": False,
            "responsive_web_enhance_cards_enabled": False
        },
        "queryId": "SoVnbfCycZ7fERGCwpZkYA"
    }

    if reply_to_id:
        payload["variables"]["reply"] = {
            "in_reply_to_tweet_id": reply_to_id,
            "exclude_reply_user_ids": []
        }

    r = session.post(GRAPHQL_URL, json=payload)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")

    rj = r.json()
    print(f"  🔍 create_tweet response: {str(rj)[:500]}")
    tweet_id = rj["data"]["create_tweet"]["tweet_results"]["result"]["rest_id"]
    return tweet_id


# ── Core ─────────────────────────────────────────────────────

def post_thread(account, tweets, acct_index):
    session    = make_session(account["auth_token"], account["ct0"])
    image_path = get_image_path(acct_index)
    first_id   = None
    last_id    = None

    for i, text in enumerate(tweets):
        media_id = None
        if i == 0 and image_path:
            print(f"  📷 Uploading image: {image_path}")
            media_id = upload_image(account["auth_token"], account["ct0"], image_path)

        tweet_id = post_tweet(session, text, reply_to_id=last_id, media_id=media_id)

        if i == 0:
            first_id = tweet_id
        last_id = tweet_id

        print(f"  ✅ Tweet {i+1}/{len(tweets)} posted (id: {tweet_id})")

        if i < len(tweets) - 1:
            delay = random.randint(8, 15)
            print(f"  ⏳ Waiting {delay}s...")
            time.sleep(delay)

    return first_id


def run():
    accounts = load_accounts()
    threads  = load_threads()
    posted   = load_posted()

    if len(accounts) != len(threads):
        print(f"⚠️  Jumlah akun ({len(accounts)}) != jumlah thread ({len(threads)})")
        return

    total = len(accounts)
    print(f"\n📋 Total akun: {total}")
    print("Pilih mode:")
    print("  1. 1 akun")
    print("  2. Semua akun")
    print("  3. Range akun")
    mode = input("\nPilihan (1/2/3): ").strip()

    if mode == "1":
        pick = int(input(f"Nomor akun (1-{total}): ").strip())
        indices = [pick]
    elif mode == "2":
        indices = list(range(1, total + 1))
    elif mode == "3":
        start = int(input(f"Dari akun (1-{total}): ").strip())
        end   = int(input(f"Sampai akun (1-{total}): ").strip())
        indices = list(range(start, end + 1))
    else:
        print("❌ Pilihan tidak valid.")
        return

    print(f"\n🚀 Akan post untuk akun: {indices}\n")

    for idx in indices:
        account = accounts[idx - 1]
        thread  = threads[idx - 1]
        print(f"\n🔑 Akun {idx}")

        if idx in posted:
            print(f"  ⏭️  Sudah pernah post → {posted[idx]} — skip.")
            continue

        try:
            first_id  = post_thread(account, thread, idx)
            tweet_url = f"https://x.com/i/web/status/{first_id}"
            save_posted(idx, tweet_url)
            print(f"  🔗 Link: {tweet_url}")
        except Exception as e:
            print(f"  ❌ Error akun {idx}: {e}")

        delay = random.randint(10, 20)
        print(f"\n⏳ Waiting {delay}s before next account...")
        time.sleep(delay)

    print("\n🏁 Done!")


if __name__ == "__main__":
    run()
