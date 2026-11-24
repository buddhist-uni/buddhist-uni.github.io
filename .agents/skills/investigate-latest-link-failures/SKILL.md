---
name: investigate-latest-link-failures
description: >-
  Investigate the latest External Links GitHub Actions failure by verifying one
  example URL per host in the user's local Chrome browser (via Chrome DevTools
  MCP) and producing a filtered report of real failing URLs. Use when the user
  invokes /investigate-latest-link-failures or asks to triage the latest
  External Links action run.
---

# Investigate Latest Link Failures

Triage the latest `External Links` (`.github/workflows/links.yml`) GitHub Actions run by separating GitHub-runner blocks and auto-resolving bot challenges from genuine broken links.

## Step 1: Prompt User to Start Local Chrome

Before running any browser checks, instruct the user to set up their local Chrome debugging instance and **stop and wait for their reply**:

1. Start Chrome in the background:
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
   ```
2. Navigate to `chrome://inspect/#remote-debugging`, ensure remote debugging is turned on, and close that settings tab.
3. Reply when ready.

Do **not** proceed to browser checks until the user confirms Chrome is ready.

## Step 2: Fetch Latest `External Links` Action Log

Once the user replies:

1. Verify `list_pages` on `chrome-devtools-plugin_chrome_devtools` succeeds.
2. Fetch the latest `External Links` (`links.yml`) run and its `Links` job log using `gh` (`BypassSandbox: true` since `gh` needs network and keyring access):
   ```bash
   gh run list --repo buddhist-uni/buddhist-uni.github.io --workflow links.yml --limit 1 --json databaseId,status,conclusion,createdAt
   ```
   Then get the `Links` job ID and download its raw log to `/tmp/gh_links_log.txt`:
   ```bash
   gh api repos/buddhist-uni/buddhist-uni.github.io/actions/runs/<RUN_ID>/jobs --jq '.jobs[] | select(.name=="Links") | .id'
   gh api repos/buddhist-uni/buddhist-uni.github.io/actions/jobs/<JOB_ID>/logs > /tmp/gh_links_log.txt
   ```

## Step 3: Extract One Example URL per `(host, status)` Pair

Run the helper script (sandboxed) to parse `## Errors per input` (up to `## Timeouts per input`) and write one example URL per unique `(host, gha_status)` pair (so a spurious `403` on a host never masks a real `404` on that same host):

```bash
python3 .agents/skills/investigate-latest-link-failures/scripts/parse_errors.py extract /tmp/gh_links_log.txt /tmp/urls_to_check.json
```

## Step 4: Verify Hosts in Local Chrome (Two-Stage Check)

Split the extracted host URLs into about 6-8 batches and launch parallel `browser` subagents (`Model: "flash"`). Instruct each subagent:

1. Open **one** blank tab (`new_page(url="about:blank", background=true)`) and use only its `pageId`.
2. **Stage 1 (Fast pass)**: For each URL:
   - Call `navigate_page(pageId=<id>, type="url", url=<url>, timeout=3000)`. (Timeout is expected on slow pages—do not retry.)
   - Call `list_network_requests(pageId=<id>, resourceTypes=["document"], pageSize=5)` to read the document HTTP status.
   - If the status is `200` (or redirects to `200`) and the title is not a bot challenge (`"Just a moment..."`, `"Checking your browser"`, `"Let's confirm you are human"`, `"Making sure you're not a bot!"`, etc), classify as `ok`.
3. **Stage 2 (Challenge wait)**: Only if Stage 1 hits a `403`, `429`, `405`, or bot-challenge title:
   - Wait ~6–8 seconds (e.g., `evaluate_script` with `async () => { await new Promise(r => setTimeout(r, 7000)); return {url: location.href, title: document.title}; }`) and re-check `list_network_requests(pageId=<id>, resourceTypes=["document"], pageSize=10)`.
   - If a subsequent `200` document request appeared and the title changed to real content, classify as `ok` (auto-resolved managed challenge).
   - Otherwise, check `get_network_request` on the `403` `reqid` for challenge headers (`cf-mitigated`) vs static origin/WAF blocks (e.g., CloudFront `403`), and the page content to classify as `hard_block` or `interactive_challenge`.
4. Close the tab (`close_page(pageId=<id>)`) when done and return JSON results.

Note: Classify as spurious (`ok`) any host whose HTML renders normally despite an origin `500` (such as `newbooksnetwork.com`). Keep as real failures: `404`, `500`/`502`/`503` error pages, `net::ERR_*` (DNS/TLS/connection failures), local timeouts, and confirmed `hard_block`s.

## Step 5: Generate the Filtered Report Artifact

Save the confirmed real-failure `(host, gha_status)` pairs (keyed as `"host|gha_status"` -> local status note) to `/tmp/keep_pairs.json`, then run:

```bash
python3 .agents/skills/investigate-latest-link-failures/scripts/parse_errors.py filter /tmp/gh_links_log.txt /tmp/keep_pairs.json /tmp/real_failing_urls.md
```

Write the resulting markdown to `real_failing_urls.md` in the conversation artifact directory (`UserFacing: true`) and link it in your final response.
