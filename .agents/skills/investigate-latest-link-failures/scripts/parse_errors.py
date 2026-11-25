#!/usr/bin/env python3
"""Parse lychee '## Errors per input' logs and filter out spurious (host, status) pairs."""

import json
import re
import sys
from collections import OrderedDict, defaultdict
from urllib.parse import urlparse


def iter_error_section(log_path: str):
    """Yield (current_file, line_content) within '## Errors per input'."""
    in_errors = False
    current_file = None
    with open(log_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            content = line.split(" ", 1)[1] if " " in line else ""
            if content == "## Errors per input":
                in_errors = True
                continue
            if in_errors and content.startswith("## ") and content != "## Errors per input":
                break
            if not in_errors:
                continue
            if content.startswith("### Errors in "):
                current_file = content.replace("### Errors in ", "", 1)
            elif content.startswith("* "):
                yield current_file, content


def cmd_extract(log_path: str, out_json: str):
    """Extract one example failing URL per unique (host, gha_status) pair."""
    pairs = OrderedDict()
    for _, content in iter_error_section(log_path):
        m = re.search(r"<(https?://[^>]+)>", content)
        if not m:
            continue
        url = m.group(1)
        host = urlparse(url).netloc.lower()
        sm = re.match(r"\* \[([^\]]+)\]", content)
        status = sm.group(1) if sm else "?"
        key = (host, status)
        if key not in pairs:
            pairs[key] = {"host": host, "gha_status": status, "url": url}

    out = [pairs[k] for k in sorted(pairs.keys())]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Extracted {len(out)} unique (host, status) pairs to {out_json}")


def cmd_filter(log_path: str, keep_pairs_json: str, out_md: str):
    """Filter log errors to only (host, status) pairs in keep_pairs_json ({'host|status': note})."""
    with open(keep_pairs_json, "r", encoding="utf-8") as f:
        keep_pairs = json.load(f)

    by_pair = defaultdict(lambda: defaultdict(list))
    total_entries = 0
    kept_entries = 0
    all_pairs = set()

    for current_file, content in iter_error_section(log_path):
        m = re.search(r"<(https?://[^>]+)>", content)
        if not m:
            continue
        url = m.group(1)
        host = urlparse(url).netloc.lower()
        sm = re.match(r"\* \[([^\]]+)\]", content)
        status = sm.group(1) if sm else "?"
        pair_key = f"{host}|{status}"
        all_pairs.add(pair_key)
        total_entries += 1
        if pair_key in keep_pairs:
            by_pair[pair_key][(status, url)].append(current_file)
            kept_entries += 1

    filtered_entries = total_entries - kept_entries
    filtered_pairs = len(all_pairs) - len(by_pair)
    unique_urls = sum(len(urls) for urls in by_pair.values())
    kept_hosts = {pk.split("|", 1)[0] for pk in by_pair}

    md = [
        "# Real Failing URLs (Filtered from GitHub Actions Log)",
        "",
        f"- **Total error entries in log**: {total_entries} (across {len(all_pairs)} `(host, status)` pairs)",
        f"- **Filtered out as spurious**: {filtered_entries} entries (across {filtered_pairs} `(host, status)` pairs)",
        f"- **Remaining real failures**: {kept_entries} entries ({unique_urls} unique URLs across {len(kept_hosts)} hosts)",
        "",
        "## Summary by Host & Status",
        "",
        "| Host | GHA Status | Unique URLs | Total Occurrences | Local Browser Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]

    for pk in sorted(by_pair.keys()):
        host, status = pk.split("|", 1)
        u_cnt = len(by_pair[pk])
        t_cnt = sum(len(files) for files in by_pair[pk].values())
        md.append(f"| `{host}` | `{status}` | {u_cnt} | {t_cnt} | {keep_pairs[pk]} |")

    md.extend(["", "## Failing URLs by Host & Status", ""])
    for pk in sorted(by_pair.keys()):
        host, status = pk.split("|", 1)
        md.append(f"### `{host}` (`[{status}]`) — {keep_pairs[pk]}")
        md.append("")
        for (st, url), files in sorted(by_pair[pk].items(), key=lambda x: x[0][1]):
            files_str = ", ".join(f"`{fn}`" for fn in files)
            md.append(f"- `[{st}]` <{url}>")
            md.append(f"  - Found in: {files_str}")
        md.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote {len(md)} lines ({unique_urls} unique URLs across {len(kept_hosts)} hosts) to {out_md}")


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_errors.py <extract|filter> ...", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "extract" and len(sys.argv) == 4:
        cmd_extract(sys.argv[2], sys.argv[3])
    elif cmd == "filter" and len(sys.argv) == 5:
        cmd_filter(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print("Invalid arguments", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
