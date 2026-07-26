# 🎵 Adam's Vinyl Record Collection

> An automated local catalog & Discogs API sync engine for my personal vinyl collection.

---

## 📌 Overview

This repository maintains a version-controlled catalog of my vinyl record collection. It originally started as an AI-powered OCR scan of physical record shelf spines, consolidated into a clean, alphabetical markdown catalog, and connected directly to the **Discogs API** to keep my online collection up-to-date automatically.

- **264+ Cataloged Albums** (The Beatles, Led Zeppelin, Pink Floyd, Steely Dan, Talking Heads, Wilco, Frank Zappa, and more)
- **Automated Discogs Sync Engine** with rate-limiting guardrails and resumption tracking
- **Duplicate Detection & Audit Suite** to keep Discogs clean

---

## 🛠️ Repository Architecture

```text
.
├── README.md                 # Project documentation
├── catalog_2026-07-26.md     # Consolidated, alphabetical vinyl collection catalog
├── discogs_sync_plan.md      # Technical architecture and API integration plan
├── sync_discogs.py           # Core script: parses markdown & syncs releases to Discogs
├── check_duplicates.py       # Audit script: inspects Discogs for duplicate releases
├── cleanup_duplicates.py     # Cleanup script: automatically removes redundant duplicate entries
└── sync_progress.json        # State file: maps local records to Discogs Release IDs
```

---

## ⚡ Quick Start

### 1. Configuration
Create a `.env.discogs` file in the root directory (this file is gitignored to protect secrets):

```env
User_Profile=https://www.discogs.com/user/adamlacasse
Personal_Token=YOUR_DISCOGS_PERSONAL_ACCESS_TOKEN
```

> **How to get your Personal Token**: Go to your [Discogs Developer Settings](https://www.discogs.com/settings/developers) $\rightarrow$ click **Generate New Token**.

---

### 2. Syncing Collection to Discogs
To parse `catalog_2026-07-26.md` and push all albums to your Discogs collection:

```bash
python3 sync_discogs.py
```

- Features rate-limit protection (`HTTP 429` backoff).
- Automatically skips items already recorded in `sync_progress.json`.

---

### 3. Duplicate Detection & Cleanup
To audit your Discogs account for any duplicate releases:

```bash
# Audit & view report
python3 check_duplicates.py

# Preview proposed deletions (dry run)
python3 cleanup_duplicates.py

# Perform automated deletion of redundant entries
python3 cleanup_duplicates.py --execute
```

---

## 🔮 Roadmap / Future Ideas

- [x] Discogs API integration & collection sync
- [x] Automated duplicate detection and cleanup tool
- [ ] Generate visual stats & breakdown (decade, genre, top artists)
- [ ] Export catalog to JSON / web component to embed on personal website
