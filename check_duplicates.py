#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import ssl
import urllib.request
import urllib.parse
from collections import defaultdict

ENV_FILE = ".env.discogs"
ssl_ctx = ssl._create_unverified_context()

def load_env(env_path=ENV_FILE):
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def parse_username(env):
    if "Username" in env:
        return env["Username"]
    if "User_Profile" in env:
        parts = env["User_Profile"].rstrip("/").split("/")
        return parts[-1]
    return None

def make_request(url, auth_header, method="GET"):
    headers = {
        "User-Agent": "DiscogsDuplicateChecker/1.0",
        "Authorization": auth_header
    }
    req = urllib.request.Request(url, headers=headers, method=method)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, context=ssl_ctx) as resp:
                remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
                if remaining is not None:
                    try:
                        if int(remaining) < 3:
                            time.sleep(10)
                    except ValueError:
                        pass
                if method == "DELETE":
                    return True
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = e.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else 60
                print(f"\n[Rate Limit] Pausing {wait_time}s...", flush=True)
                time.sleep(wait_time)
                continue
            if method == "DELETE" and e.code == 204:
                return True
            raise Exception(f"HTTP {e.code} {e.reason}")
    raise Exception("Max retries exceeded")

def clean_artist_name(name):
    return re.sub(r"\s*\(\d+\)$", "", name).strip()

def normalize_key(artist, album):
    a_clean = clean_artist_name(artist).lower()
    t_clean = album.lower()
    a_clean = re.sub(r"[^\w\s]", "", a_clean).strip()
    t_clean = re.sub(r"[^\w\s]", "", t_clean).strip()
    return (a_clean, t_clean)

def fetch_all_collection_items(username, auth_header):
    print(f"Fetching collection items for user '{username}' from Discogs...")
    items = []
    page = 1
    total_pages = 1
    
    while page <= total_pages:
        url = f"https://api.discogs.com/users/{username}/collection/folders/0/releases?per_page=100&page={page}"
        print(f"  Fetching page {page}/{total_pages}...", end=" ", flush=True)
        data = make_request(url, auth_header)
        
        pagination = data.get("pagination", {})
        total_pages = pagination.get("pages", 1)
        
        releases = data.get("releases", [])
        items.extend(releases)
        print(f"Got {len(releases)} items (Total fetched: {len(items)})")
        
        page += 1
        time.sleep(1.0)
        
    return items

def analyze_duplicates(items):
    grouped = defaultdict(list)
    
    for item in items:
        basic = item.get("basic_information", {})
        artists = basic.get("artists", [])
        artist_name = ", ".join([a.get("name", "") for a in artists]) if artists else "Unknown Artist"
        title = basic.get("title", "Unknown Title")
        release_id = basic.get("id")
        instance_id = item.get("instance_id")
        folder_id = item.get("folder_id", 1)
        formats = basic.get("formats", [])
        fmt_str = ", ".join([f.get("name", "") for f in formats]) if formats else ""

        key = normalize_key(artist_name, title)
        
        grouped[key].append({
            "artist": clean_artist_name(artist_name),
            "title": title,
            "release_id": release_id,
            "instance_id": instance_id,
            "folder_id": folder_id,
            "format": fmt_str,
            "date_added": item.get("date_added")
        })
        
    duplicates = {k: v for k, v in grouped.items() if len(v) > 1}
    return grouped, duplicates

def delete_instance(username, folder_id, release_id, instance_id, auth_header):
    url = f"https://api.discogs.com/users/{username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}"
    make_request(url, auth_header, method="DELETE")

def main():
    env = load_env()
    token = env.get("Personal_Token") or env.get("DISCOGS_TOKEN")
    username = parse_username(env)
    
    if not token or not username:
        print("Error: Personal_Token or Username missing in .env.discogs")
        sys.exit(1)
        
    auth_header = f"Discogs token={token}"
    
    items = fetch_all_collection_items(username, auth_header)
    grouped, duplicates = analyze_duplicates(items)
    
    print(f"\n==========================================")
    print(f" DISCOGS COLLECTION DUPLICATE REPORT")
    print(f" Total Items in Collection: {len(items)}")
    print(f" Unique Artist/Album Pairs: {len(grouped)}")
    print(f" Duplicate Groups Found   : {len(duplicates)}")
    print(f"==========================================\n")
    
    if not duplicates:
        print("🎉 No duplicate artist/album pairs found in your Discogs collection!")
        return

    print("Found the following duplicate albums in your collection:\n")
    for idx, (key, dup_list) in enumerate(duplicates.items(), 1):
        display_artist = dup_list[0]["artist"]
        display_title = dup_list[0]["title"]
        print(f"{idx}. {display_artist} - '{display_title}' ({len(dup_list)} copies)")
        for item in dup_list:
            print(f"   • Instance ID: {item['instance_id']} | Release ID: {item['release_id']} | Format: {item['format']} | Added: {item['date_added']}")
        print()

if __name__ == "__main__":
    main()
