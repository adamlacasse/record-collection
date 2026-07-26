# Discogs Sync Plan

This document outlines the plan to read the vinyl collection from `catalog_2026-07-26.md` and add those albums to your Discogs collection using the Discogs API.

## 1. Prerequisites
- **Discogs Account**: You need a Discogs user account.
- **API Credentials**: Generate a Personal Access Token from your Discogs developer settings.
- **Environment**: We need to choose a programming language (e.g., Python or Node.js) to write the script. Python with the `requests` or `discogs-client` library is highly recommended for this kind of scripting.

## 2. Script Workflow
The script will perform the following steps:

1. **Parse the Markdown File**: Read `catalog_2026-07-26.md` and extract the artist and album title using regular expressions. We will handle edge cases like "(2 copies)", box sets, and split lines (e.g., "*Eat a Peach* / *Live at Fillmore East*").
2. **Search the Discogs API**: For each artist and album pair, query the Discogs database (`GET /database/search`) to find the corresponding `release_id`.
3. **Handle Ambiguity**:
    - If a specific pressing is known, it should be selected.
    - If not, the script can default to adding the most popular or master release, or we can make the script interactive so you can select the correct pressing from the search results.
4. **Add to Collection**: Make a POST request to the Discogs API (`POST /users/{username}/collection/folders/{folder_id}/releases/{release_id}`) to add the album to your collection. We'll add it to the "Uncategorized" folder (folder ID `0`) unless specified otherwise.
5. **Rate Limiting**: Discogs API limits requests to 60 per minute. The script will need to include `sleep()` calls to respect this limit.

## 3. Open Questions
Before we start writing the code, please let me know:
1. **Language Choice**: Do you prefer Python, Node.js, or something else for the script?
2. **Ambiguity Handling**: Some albums have dozens of pressings. Do you want the script to just pick the first match/master release automatically, or do you want it to prompt you in the terminal when there are multiple matches?
3. **API Token**: Do you already have a Discogs Personal Access Token ready to use?

## 4. Next Steps
Once we align on the questions above, we can write the script, set up the environment, and run it to sync the collection!
