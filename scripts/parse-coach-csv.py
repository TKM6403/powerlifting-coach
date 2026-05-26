#!/usr/bin/env python3
"""
parse-coach-csv.py

Convert coach-prescribed CSV programs into markdown summaries for reference.

Expected CSV columns (flexible — script handles common formats):
- Week, Day, Exercise, Sets, Reps, RPE (or Load %), Notes

Usage:
    python scripts/parse-coach-csv.py [path/to/csvs]

If no path given, defaults to reference/past-coach-programs/

Generates a corresponding .md file alongside each .csv with:
- Block summary (weeks, sessions per week, lifts covered)
- Weekly structure tables
- Notable patterns (RPE progression, volume trends)

Edit the column name mappings at the top if your coach uses different headers.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# ---- Configurable column name mappings ----
# If your coach's CSVs use different column names, adjust these.
COLUMN_ALIASES = {
    'week': ['week', 'wk', 'week_number'],
    'day': ['day', 'session', 'workout_day'],
    'exercise': ['exercise', 'lift', 'movement'],
    'sets': ['sets', 'set'],
    'reps': ['reps', 'rep', 'repetitions'],
    'rpe': ['rpe', 'rpe_target', 'intensity_rpe'],
    'load': ['load', 'weight', 'percent', '%', 'load_pct', 'percentage'],
    'notes': ['notes', 'note', 'comment', 'comments'],
}


def normalize_header(header):
    """Map a CSV header to a standard column name."""
    h = header.strip().lower()
    for canonical, aliases in COLUMN_ALIASES.items():
        if h in aliases:
            return canonical
    return h


def parse_csv(csv_path):
    """Parse a single coach CSV. Returns list of dicts with normalized keys."""
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        normalized = [normalize_header(h) for h in headers]
        rows = []
        for raw_row in reader:
            row = dict(zip(normalized, raw_row))
            rows.append(row)
    return rows


def summarize(rows, csv_name):
    """Produce a markdown summary from the parsed rows."""
    out = [f"# Coach Program Summary: {csv_name}", ""]

    weeks = sorted({r.get('week', '') for r in rows if r.get('week')})
    days = sorted({r.get('day', '') for r in rows if r.get('day')})
    exercises = sorted({r.get('exercise', '') for r in rows if r.get('exercise')})

    out.append("## Overview")
    out.append("")
    out.append(f"- **Total weeks:** {len(weeks)}")
    out.append(f"- **Sessions per week:** {len(days)}")
    out.append(f"- **Unique exercises:** {len(exercises)}")
    out.append("")

    out.append("## Exercises Programmed")
    out.append("")
    for ex in exercises:
        out.append(f"- {ex}")
    out.append("")

    # Group by week, then by day
    by_week = defaultdict(lambda: defaultdict(list))
    for r in rows:
        wk = r.get('week', 'Unknown')
        day = r.get('day', 'Unknown')
        by_week[wk][day].append(r)

    out.append("## Weekly Structure")
    out.append("")

    for wk in weeks:
        out.append(f"### Week {wk}")
        out.append("")
        for day in days:
            entries = by_week[wk].get(day, [])
            if not entries:
                continue
            out.append(f"**{day}**")
            out.append("")
            out.append("| Exercise | Sets | Reps | RPE | Load | Notes |")
            out.append("|---|---|---|---|---|---|")
            for e in entries:
                row = [
                    e.get('exercise', ''),
                    e.get('sets', ''),
                    e.get('reps', ''),
                    e.get('rpe', ''),
                    e.get('load', ''),
                    e.get('notes', ''),
                ]
                # Pipe-escape any pipes inside cells
                row = [c.replace('|', '\\|') for c in row]
                out.append('| ' + ' | '.join(row) + ' |')
            out.append("")

    # RPE progression check
    rpe_by_week = defaultdict(list)
    for r in rows:
        wk = r.get('week', '')
        rpe = r.get('rpe', '')
        try:
            rpe_val = float(rpe)
            rpe_by_week[wk].append(rpe_val)
        except (ValueError, TypeError):
            continue

    if rpe_by_week:
        out.append("## RPE Trend")
        out.append("")
        out.append("| Week | Avg RPE | Max RPE |")
        out.append("|---|---|---|")
        for wk in sorted(rpe_by_week.keys()):
            vals = rpe_by_week[wk]
            avg = sum(vals) / len(vals) if vals else 0
            mx = max(vals) if vals else 0
            out.append(f"| {wk} | {avg:.1f} | {mx:.1f} |")
        out.append("")

    out.append("## Notes for SBD Agent")
    out.append("")
    out.append("- Use this as style reference for how tkm's human coach periodizes")
    out.append("- Reference RPE trend when designing new blocks")
    out.append("- Pay attention to variation selection across the block")
    out.append("")

    return "\n".join(out)


def main():
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
    else:
        target_dir = Path(__file__).parent.parent / "reference" / "past-coach-programs"

    if not target_dir.exists():
        print(f"Directory not found: {target_dir}")
        sys.exit(1)

    csvs = list(target_dir.glob("*.csv"))
    if not csvs:
        print(f"No CSV files found in {target_dir}")
        sys.exit(0)

    for csv_path in csvs:
        print(f"Processing {csv_path.name}...")
        try:
            rows = parse_csv(csv_path)
            summary = summarize(rows, csv_path.stem)
            md_path = csv_path.with_suffix('.md')
            md_path.write_text(summary, encoding='utf-8')
            print(f"  → wrote {md_path.name}")
        except Exception as e:
            print(f"  ! error processing {csv_path.name}: {e}")

    print("Done.")


if __name__ == '__main__':
    main()
