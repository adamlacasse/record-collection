#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import ssl
import urllib.request
import urllib.parse

ENV_FILE = ".env.discogs"
CATALOG_FILE = "catalog_2026-07-26.md"
PROGRESS_FILE = "sync_progress.json"

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

def save_env_kv(key, value, env_path=ENV_FILE):
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def parse_username(env):
    if "Username" in env:
        return env["Username"]
    if "User_Profile" in env:
        parts = env["User_Profile"].rstrip("/").split("/")
        return parts[-1]
    return None

def parse_catalog(filepath=CATALOG_FILE):
    items = []
    if not os.path.exists(filepath):
        print(f"Error: Catalog file '{filepath}' not found.")
        sys.exit(1)
        
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("* **"):
                continue
            m = re.match(r"^\*\s*\*\*(.*?)\*\*\s*[\u2013\u2014\-]\s*(.*)$", line)
            if not m:
                continue
            artist = m.group(1).strip()
            rest = m.group(2).strip()
            
            count = 1
            count_match = re.search(r"\((\d+)\s+copies(?:\/pressings)?\)", rest, re.IGNORECASE)
            if count_match:
                count = int(count_match.group(1))
            
            albums = re.findall(r"\*(.*?)\*", rest)
            if not albums:
                clean_rest = re.sub(r"\s*\([^)]*\)\s*$", "", rest)
                albums = [clean_rest]
            
            for album in albums:
                album_clean = album.strip()
                if album_clean:
                    items.append({
                        "artist": artist,
                        "album": album_clean,
                        "count": count
                    })
    return items

def make_request(url, method="GET", headers=None, data=None, retries=5):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "RecordCollectionSyncScript/1.0"
    
    encoded_data = None
    if data is not None:
        if isinstance(data, dict):
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif isinstance(data, bytes):
            encoded_data = data
        else:
            encoded_data = str(data).encode("utf-8")
            
    for attempt in range(retries):
        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=ssl_ctx) as resp:
                # Check rate limit header
                remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
                if remaining is not None:
                    try:
                        rem_val = int(remaining)
                        if rem_val < 3:
                            time.sleep(10)
                    except ValueError:
                        pass

                resp_body = resp.read().decode("utf-8")
                if resp_body:
                    try:
                        return json.loads(resp_body)
                    except json.JSONDecodeError:
                        return resp_body
                return {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = e.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else 60
                print(f"\n[Rate Limit hit] Pausing for {wait_time} seconds before retrying (attempt {attempt+1}/{retries})...", flush=True)
                time.sleep(wait_time)
                continue
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("message", err_body)
            except Exception:
                err_msg = err_body
            raise Exception(f"HTTP {e.code} {e.reason}: {err_msg}")
    
    raise Exception("Max retries exceeded due to rate limiting (HTTP 429)")

def authenticate(env):
    username = parse_username(env)
    if not username:
        print("Error: Username or User_Profile missing in .env.discogs")
        sys.exit(1)
        
    personal_token = env.get("Personal_Token") or env.get("DISCOGS_TOKEN")
    if personal_token:
        print(f"Authenticated using Personal Access Token for user '{username}'.")
        auth_header = f"Discogs token={personal_token}"
        return username, auth_header

    access_token = env.get("Access_Token")
    access_secret = env.get("Access_Token_Secret")
    consumer_key = env.get("Consumer_Key")
    consumer_secret = env.get("Consumer_Secret")

    if access_token and access_secret and consumer_key and consumer_secret:
        print(f"Authenticated using OAuth Access Token for user '{username}'.")
        auth_header = (
            f'OAuth oauth_consumer_key="{consumer_key}", '
            f'oauth_token="{access_token}", '
            f'oauth_signature="{consumer_secret}&{access_secret}", '
            f'oauth_signature_method="PLAINTEXT", '
            f'oauth_timestamp="{int(time.time())}", '
            f'oauth_nonce="{int(time.time())}"'
        )
        return username, auth_header

    print("Error: Neither Personal Access Token nor Consumer Key/Secret available.")
    sys.exit(1)

def search_release(artist, album, auth_header):
    query_params = {
        "artist": artist,
        "release_title": album,
        "type": "release",
        "per_page": 5
    }
    url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(query_params)}"
    headers = {"Authorization": auth_header}
    
    res = make_request(url, headers=headers)
    time.sleep(1.5)
    results = res.get("results", [])
    
    if not results:
        general_query = {"q": f"{artist} {album}", "type": "release", "per_page": 5}
        url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(general_query)}"
        res = make_request(url, headers=headers)
        time.sleep(1.5)
        results = res.get("results", [])
        
    if not results:
        master_query = {"q": f"{artist} {album}", "type": "master", "per_page": 5}
        url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(master_query)}"
        res = make_request(url, headers=headers)
        time.sleep(1.5)
        results = res.get("results", [])
        if results and "main_release" in results[0]:
            return results[0]["main_release"], results[0].get("title", f"{artist} - {album}")

    if results:
        return results[0]["id"], results[0].get("title", f"{artist} - {album}")
    
    return None, None

def add_to_collection(username, release_id, auth_header):
    url = f"https://api.discogs.com/users/{username}/collection/folders/1/releases/{release_id}"
    headers = {"Authorization": auth_header}
    res = make_request(url, method="POST", headers=headers)
    return res

def main():
    env = load_env()
    username, auth_header = authenticate(env)
    
    items = parse_catalog()
    print(f"Loaded {len(items)} albums from {CATALOG_FILE}.")
    
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                progress = json.load(f)
            except Exception:
                progress = {}
                
    success_count = sum(1 for v in progress.values() if v.get("status") == "added")
    skipped_count = 0
    not_found_list = []

    print("\nResuming Discogs collection sync with automatic 429 rate-limit backoff...")
    for idx, item in enumerate(items, 1):
        artist = item["artist"]
        album = item["album"]
        count = item["count"]
        key = f"{artist} - {album}"

        if key in progress and progress[key].get("status") == "added":
            skipped_count += 1
            continue

        print(f"[{idx}/{len(items)}] Searching: {key}...", end=" ", flush=True)
        
        try:
            release_id, matched_title = search_release(artist, album, auth_header)
            
            if not release_id:
                print("❌ NOT FOUND")
                progress[key] = {"status": "not_found"}
                not_found_list.append(key)
            else:
                for c in range(count):
                    add_to_collection(username, release_id, auth_header)
                    time.sleep(1.5)
                        
                print(f"✅ ADDED (ID: {release_id}) -> '{matched_title}'")
                progress[key] = {
                    "status": "added",
                    "release_id": release_id,
                    "matched_title": matched_title,
                    "count": count
                }
                success_count += 1
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            progress[key] = {"status": "error", "error": str(e)}

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2)

    print("\n--- Sync Summary ---")
    print(f"Total Albums Processed: {len(items)}")
    print(f"Successfully Added: {success_count}")
    print(f"Not Found: {len(not_found_list)}")
    if not_found_list:
        print("\nAlbums not found on Discogs:")
        for nf in not_found_list:
            print(f" - {nf}")

if __name__ == "__main__":
    main()
