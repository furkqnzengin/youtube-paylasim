#!/usr/bin/env python3
"""Sıradaki videoyu YouTube'a yükler.

Kullanım:
  python scripts/upload.py --plan      # kuyruğu ve üretilecek başlıkları göster
  python scripts/upload.py --dry-run   # sıradakini seç, yüklemeden göster
  python scripts/upload.py             # sıradakini yükle ve state'e kaydet
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "videos"
STATE = ROOT / "state" / "published.json"
CATEGORIES = ROOT / "metadata" / "categories.json"
OVERRIDES = ROOT / "metadata" / "overrides.json"

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def split_category(stem, categories):
    """'rays_heart' -> ('rays', 'heart'). En uzun eşleşen ön ek kazanır."""
    for prefix in sorted(categories, key=len, reverse=True):
        if stem == prefix:
            return prefix, ""
        if stem.startswith(prefix + "_"):
            return prefix, stem[len(prefix) + 1:]
    return None, stem


def humanize(variant, names):
    """'9fold' -> '9-Fold', '50deg' -> '50°', 'star5' -> 'Star 5'."""
    if variant in names:
        return names[variant]
    words = []
    for part in variant.split("_"):
        if not part:
            continue
        if part in names:
            words.append(names[part])
            continue
        m = re.fullmatch(r"(\d+)deg", part)
        if m:
            words.append(m.group(1) + "°")
            continue
        m = re.fullmatch(r"(\d+)fold", part)
        if m:
            words.append(m.group(1) + "-Fold")
            continue
        pieces = re.findall(r"\d+|[^\d]+", part)
        words.extend(p if p.isdigit() else p.capitalize() for p in pieces)
    return " ".join(words)


def build_metadata(filename, config, overrides):
    stem = Path(filename).stem
    cats = config.get("categories", {})
    cat, variant = split_category(stem, cats)
    variant_text = humanize(variant, config.get("variant_names", {}))
    if cat:
        base = cats[cat]["title"]
        title = f"{base} – {variant_text}" if variant_text else base
        tags = list(cats[cat].get("tags", []))
    else:
        title = variant_text
        tags = []
    suffix = config.get("title_suffix")
    if suffix:
        title = f"{title} | {suffix}"
    tags = list(dict.fromkeys(config.get("common_tags", []) + tags))

    ov = overrides.get(filename, {})
    title = ov.get("title", title)[:100]
    tags = ov.get("tags", tags)
    hashtags = " ".join("#" + t for t in tags)
    description = ov.get("description") or config.get(
        "description", "{title}\n\n{hashtags}"
    ).format(title=title, hashtags=hashtags)
    return {"title": title, "description": description[:5000], "tags": tags,
            "category": cat or "other"}


def pending_videos(published):
    done = {p["file"] for p in published}
    return sorted(
        f.name for f in VIDEOS.iterdir()
        if f.suffix.lower() in VIDEO_EXTS and f.name not in done
    )


def pick_next(pending, published, config):
    """Aynı tür art arda gelmesin: son yayınlanandan farklı ve en çok
    videosu kalan türden, alfabetik ilk videoyu seç."""
    if not pending:
        return None
    cats = config.get("categories", {})
    groups = {}
    for name in pending:
        cat = split_category(Path(name).stem, cats)[0] or "other"
        groups.setdefault(cat, []).append(name)
    last = published[-1].get("category") if published else None
    candidates = [c for c in groups if c != last] or list(groups)
    best = sorted(candidates, key=lambda c: (-len(groups[c]), c))[0]
    return groups[best][0]


def get_access_token(session):
    r = session.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Token alınamadı ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def upload(session, path, meta, privacy):
    token = get_access_token(session)
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": "28",  # Science & Technology
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    size = path.stat().st_size
    r = session.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Upload-Content-Type": "video/*",
            "X-Upload-Content-Length": str(size),
        },
        json=body, timeout=60,
    )
    if r.status_code != 200:
        sys.exit(f"Yükleme başlatılamadı ({r.status_code}): {r.text}")
    with path.open("rb") as fh:
        r = session.put(
            r.headers["Location"], data=fh,
            headers={"Content-Type": "video/*", "Content-Length": str(size)},
            timeout=1800,
        )
    if r.status_code not in (200, 201):
        sys.exit(f"Yükleme başarısız ({r.status_code}): {r.text}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="tüm kuyruğu göster")
    ap.add_argument("--dry-run", action="store_true", help="yüklemeden göster")
    ap.add_argument("--privacy", default=os.environ.get("YT_PRIVACY", "public"),
                    choices=["public", "unlisted", "private"])
    args = ap.parse_args()

    config = load_json(CATEGORIES, {})
    overrides = load_json(OVERRIDES, {})
    published = load_json(STATE, [])
    pending = pending_videos(published)

    if args.plan:
        sim, left = list(published), list(pending)
        n = 0
        while left:
            name = pick_next(left, sim, config)
            meta = build_metadata(name, config, overrides)
            n += 1
            print(f"{n:3}. {name:32} -> {meta['title']}")
            sim.append({"file": name, "category": meta["category"]})
            left.remove(name)
        print(f"\nBekleyen: {n}, yayınlanmış: {len(published)}")
        return

    name = pick_next(pending, published, config)
    if not name:
        print("Kuyrukta video kalmadı.")
        return
    meta = build_metadata(name, config, overrides)
    print(f"Sıradaki: {name}\nBaşlık:   {meta['title']}\nGizlilik: {args.privacy}")
    if args.dry_run:
        print("\n" + meta["description"])
        return

    import requests
    result = upload(requests.Session(), VIDEOS / name, meta, args.privacy)
    published.append({
        "file": name,
        "category": meta["category"],
        "title": meta["title"],
        "video_id": result["id"],
        "privacy": result.get("status", {}).get("privacyStatus"),
        "published_at": datetime.datetime.now(datetime.timezone.utc)
                        .isoformat(timespec="seconds"),
    })
    STATE.write_text(json.dumps(published, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"Yüklendi: https://youtube.com/shorts/{result['id']}")


if __name__ == "__main__":
    main()
