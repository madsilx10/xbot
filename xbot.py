import asyncio
import os
import random
from twikit import Client

# ── File paths ──────────────────────────────────────────────
ACCOUNTS_FILE = "accounts.txt"
TWEETS_FILE   = "tweets.txt"
POSTED_FILE   = "posted.txt"
IMAGES_DIR    = "images"

# ── Helpers ─────────────────────────────────────────────────

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
    """Separator antar akun: ---
    Separator antar tweet dalam thread: baris kosong
    """
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


def get_media_type(image_path):
    ext = image_path.rsplit(".", 1)[-1].lower()
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mapping.get(ext, "image/jpeg")


# ── Core ─────────────────────────────────────────────────────

async def post_thread(client, tweets, acct_index):
    image_path     = get_image_path(acct_index)
    first_tweet_id = None
    reply_to_id    = None

    for i, text in enumerate(tweets):
        media_ids = None

        # Attach image to first tweet only
        if i == 0 and image_path:
            print(f"  📷 Uploading image: {image_path}")
            media_type = get_media_type(image_path)
            media_id = await client.upload_media(
                image_path,
                media_type=media_type,
                wait_for_completion=True
            )
            media_ids = [str(media_id)]

        if reply_to_id is None:
            tweet = await client.create_tweet(text=text, media_ids=media_ids)
        else:
            # pass reply_to as string id
            tweet = await client.create_tweet(
                text=text,
                reply_to=reply_to_id,
                media_ids=media_ids
            )

        reply_to_id = tweet.id
        if i == 0:
            first_tweet_id = tweet.id

        print(f"  ✅ Tweet {i+1}/{len(tweets)} posted (id: {tweet.id})")

        # delay lebih panjang antar reply biar ga kena rate limit X
        if i < len(tweets) - 1:
            delay = random.randint(8, 15)
            print(f"  ⏳ Waiting {delay}s before next reply...")
            await asyncio.sleep(delay)

    return first_tweet_id


async def run():
    accounts = load_accounts()
    threads  = load_threads()
    posted   = load_posted()

    if len(accounts) != len(threads):
        print(f"⚠️  Jumlah akun ({len(accounts)}) != jumlah thread ({len(threads)})")
        print("Pastikan urutan akun & thread di file sama.")
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

        client = Client(language="en-US")
        client.set_cookies({
            "auth_token": account["auth_token"],
            "ct0":        account["ct0"],
        })

        try:
            first_id = await post_thread(client, thread, idx)
            tweet_url = f"https://x.com/i/web/status/{first_id}"
            save_posted(idx, tweet_url)
            print(f"  🔗 Link: {tweet_url}")
        except Exception as e:
            print(f"  ❌ Error akun {idx}: {e}")

        # delay antar akun
        delay = random.randint(10, 20)
        print(f"\n⏳ Waiting {delay}s before next account...")
        await asyncio.sleep(delay)

    print("\n🏁 Done!")


if __name__ == "__main__":
    asyncio.run(run())
