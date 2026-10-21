#!/usr/bin/env python3
"""Build the profile from public GitHub metadata. Python standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'Eraj-Choriev'
ZONE = ZoneInfo('Asia/Dushanbe')
COLORS = {'JavaScript': '#e4bd66', 'HTML': '#e68c78', 'CSS': '#a994d6', 'TypeScript': '#6fadd8', 'Python': '#75baaa'}
THEMES = {
    'dark': dict(bg='#13212c', panel='#1b2d39', ink='#edf4f5', muted='#a0b2bf', line='#344a58', teal='#83d4c2', gold='#e4bd66'),
    'light': dict(bg='#f5f9fa', panel='#e8f1f3', ink='#18333e', muted='#526c79', line='#ccdce1', teal='#227d70', gold='#906c28'),
}
PROJECTS = [
    ('Aqly', 'saas-landing', 'Bilingual AI agency landing with reusable components and motion.', 'Next.js · TypeScript · Tailwind · Motion', 'https://saaslanding-rosy.vercel.app'),
    ('Neru', 'neru-v2', 'EV charging station finder for Dushanbe, with a map-based interface.', 'JavaScript · Maps · Progressive web app', 'https://neru-v2.vercel.app'),
    ('Token Lens', 'token-lens', 'AI usage dashboard interface with charts, analytics and account screens.', 'React · Vite · Recharts · Firebase', 'https://parcel-one-blond.vercel.app'),
]


def api(path: str):
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        request = Request('https://api.github.com/' + path, headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Eraj-Choriev-profile',
        })
        with urlopen(request, timeout=30) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise RuntimeError('GitHub response exceeds the expected size')
        return json.loads(data)
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def pages(path: str):
    result = []
    for number in range(1, 21):
        batch = api(path + ('&' if '?' in path else '?') + urlencode({'per_page': 100, 'page': number}))
        if not isinstance(batch, list):
            raise ValueError('Expected a GitHub list')
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise RuntimeError('Pagination limit reached; keeping the previous dashboard')


def collect():
    now = datetime.now(ZONE)
    monday = now.date() - timedelta(days=now.weekday())
    start = monday - timedelta(weeks=11)
    since = datetime.combine(start, datetime.min.time(), tzinfo=ZONE).astimezone(timezone.utc).isoformat()
    until = now.astimezone(timezone.utc).isoformat()
    repositories = [r for r in pages(f'users/{OWNER}/repos?type=owner&sort=full_name')
                    if not r['private'] and not r['fork'] and r['name'].lower() != OWNER.lower()]
    languages = Counter(r['language'] for r in repositories if r.get('language'))
    weekly = [0] * 12
    dates = []
    for repository in repositories:
        if not repository.get('size') or (repository.get('pushed_at') or '') < since[:10]:
            continue
        params = urlencode({'author': OWNER, 'since': since, 'until': until})
        commits = pages(f'repos/{OWNER}/{repository["name"]}/commits?{params}')
        seen = set()
        for commit in commits:
            if commit['sha'] in seen:
                continue
            seen.add(commit['sha'])
            date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')).astimezone(ZONE).date()
            index = (date - start).days // 7
            if 0 <= index < 12 and date <= now.date():
                weekly[index] += 1
                dates.append(date.isoformat())
    return dict(
        owner=OWNER, updatedAt=now.isoformat(timespec='seconds'), timezone='Asia/Dushanbe',
        periodStart=start.isoformat(), periodEnd=now.date().isoformat(),
        projectCount=len(repositories), languageCount=len(languages),
        demoCount=sum(bool(r.get('homepage')) for r in repositories),
        languages=dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        repositories=[dict(name=r['name'], language=r.get('language'), url=r['html_url'], homepage=r.get('homepage') or '') for r in repositories],
        weeks=[dict(start=(start + timedelta(weeks=i)).isoformat(), commits=count) for i, count in enumerate(weekly)],
        commitCount=sum(weekly), activeDays=len(set(dates)),
    )


class SVG:
    def __init__(self, width, height, title, description, theme):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
                      '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}</style>']
        self.t = THEMES[theme]
        self.rect(0, 0, width, height, self.t['bg'], rx=16)

    def rect(self, x, y, width, height, fill, rx=0, **attrs):
        extra = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        self.parts.append(f'<rect x="{x}" y="{y}" width="{max(0, width)}" height="{max(0, height)}" rx="{rx}" fill="{fill}" {extra}/>')

    def text(self, x, y, text, size=16, color=None, weight=400, anchor='start'):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or self.t["ink"]}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(text))}</text>')

    def line(self, x1, y1, x2, y2, color=None):
        self.parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color or self.t["line"]}"/>')

    def save(self, path):
        path.write_text(''.join(self.parts) + '</svg>\n')


def hero(theme, mobile=False):
    if mobile:
        s = SVG(440, 218, 'Eraj Choriev — Frontend developer', 'React, Next.js and TypeScript. Product interfaces and dashboards.', theme)
        t = s.t
        s.rect(22, 26, 4, 163, t['teal'], rx=2)
        s.text(44, 54, 'Frontend developer', 17, t['teal'], 500)
        s.text(41, 109, 'Eraj Choriev', 43, weight=650)
        s.text(44, 146, 'Product interfaces. Thoughtful details.', 16, t['muted'])
        s.text(44, 183, 'React  /  Next.js  /  TypeScript', 15, t['muted'])
        s.save(ROOT / f'assets/intro-{theme}-mobile.svg')
        return
    s = SVG(900, 245, 'Eraj Choriev — Frontend developer', 'React, Next.js and TypeScript. Product interfaces, dashboards and web experiences.', theme)
    t = s.t
    s.rect(34, 35, 4, 172, t['teal'], rx=2)
    s.text(59, 63, 'Frontend developer', 18, t['teal'], 500)
    s.text(56, 122, 'Eraj Choriev', 52, weight=650)
    s.text(59, 163, 'Product interfaces. Thoughtful details.', 21, t['muted'])
    s.text(59, 201, 'React  /  Next.js  /  TypeScript', 17, t['muted'])
    # An interface study reflects the actual focus of the portfolio.
    s.rect(635, 43, 224, 159, t['panel'], rx=11, stroke=t['line'])
    s.line(635, 72, 859, 72)
    for x, color in [(650, t['teal']), (661, t['gold']), (672, t['muted'])]:
        s.parts.append(f'<circle cx="{x}" cy="58" r="3" fill="{color}"/>')
    s.rect(651, 88, 42, 98, t['bg'], rx=4)
    for y, width in [(101, 25), (113, 20), (125, 27)]:
        s.rect(658, y, width, 3, t['line'], rx=1)
    s.rect(706, 88, 136, 19, t['bg'], rx=4)
    s.rect(706, 120, 78, 66, t['teal'], rx=5)
    s.parts.append(f'<path d="M716,169 L731,157 L745,161 L759,143 L774,132" fill="none" stroke="{t["bg"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    for y, width in [(123, 42), (139, 33), (155, 41), (171, 25)]:
        s.rect(799, y, width, 5, t['line'], rx=2)
    s.save(ROOT / f'assets/intro-{theme}.svg')


def dashboard(data, theme, mobile=False):
    w, h = (440, 870) if mobile else (900, 520)
    s = SVG(w, h, 'Public work dashboard', f'{data["projectCount"]} public projects, {data["languageCount"]} primary languages, {data["commitCount"]} public default-branch commits in the displayed twelve weeks.', theme)
    t, pad = s.t, 28 if mobile else 34
    s.text(pad, 43, 'Public work, at a glance', 22, weight=600)
    s.text(pad, 68, f'Updated {data["periodEnd"]} · UTC+5', 13, t['muted'])
    metrics = [('Public projects', data['projectCount']), ('Primary languages', data['languageCount']), ('Linked demos', data['demoCount'])]
    for i, (label, value) in enumerate(metrics):
        x = pad + i * ((w - 2 * pad) / 3)
        s.text(x, 123, value, 38 if mobile else 44, t['teal'] if i == 0 else t['ink'], 600)
        s.text(x, 149, label, 12 if mobile else 15, t['muted'])
    s.line(pad, 176, w - pad, 176)
    # Activity: one bar per calendar week, zero weeks remain visibly zero.
    x, y, chartw = pad, 208, w - 2 * pad if mobile else 450
    s.text(x, y, 'Public commits', 19, weight=600)
    s.text(x, y + 24, f'{data["commitCount"]} commits · {data["activeDays"]} active days', 14, t['muted'])
    bottom, top, maximum = y + 171, y + 61, max(1, max(week['commits'] for week in data['weeks']))
    for ratio in [0, .5, 1]:
        pos = bottom - (bottom - top) * ratio
        s.line(x, pos, x + chartw, pos)
        s.text(x + chartw, pos - 6, str(round(maximum * ratio)), 11, t['muted'], anchor='end')
    step = chartw / 12
    for i, week in enumerate(data['weeks']):
        height = week['commits'] / maximum * (bottom - top)
        s.rect(x + i * step + 4, bottom - height, step - 10, height, t['teal'], rx=3)
        if week['commits']:
            s.text(x + (i + .5) * step - 1, bottom - height - 7, week['commits'], 11, t['ink'], anchor='middle')
    first = datetime.fromisoformat(data['periodStart']).strftime('%d %b')
    last = datetime.fromisoformat(data['periodEnd']).strftime('%d %b')
    s.text(x, bottom + 22, first, 12, t['muted'])
    s.text(x + chartw, bottom + 22, last, 12, t['muted'], anchor='end')
    s.text(x, bottom + 49, '12 weeks · default branches · attributed to this account', 10 if mobile else 12, t['muted'])
    lx, ly = (pad, 497) if mobile else (554, 208)
    s.text(lx, ly, 'Languages across projects', 19, weight=600)
    s.text(lx, ly + 24, 'Primary language per repository', 14, t['muted'])
    total = sum(data['languages'].values())
    offset, length = 0, w - 2 * pad if mobile else 312
    for language, count in data['languages'].items():
        width = count / max(1, total) * length
        s.rect(lx + offset, ly + 44, width, 12, COLORS.get(language, t['muted']))
        offset += width
    for i, (language, count) in enumerate(data['languages'].items()):
        row = ly + 88 + i * 29
        s.rect(lx, row - 10, 9, 9, COLORS.get(language, t['muted']), rx=2)
        s.text(lx + 21, row, language, 14)
        s.text(lx + length, row, f'{count} projects', 13, t['muted'], anchor='end')
    foot = h - (55 if mobile else 49)
    s.line(pad, foot - 17, w - pad, foot - 17)
    s.text(pad, foot + 2, 'Source: GitHub public API · profile repository excluded', 10 if mobile else 12, t['muted'])
    s.text(pad, foot + 22, 'Language share describes projects, not expertise or time spent.', 10 if mobile else 12, t['muted'])
    s.save(ROOT / f'assets/dashboard-{theme}{"-mobile" if mobile else ""}.svg')


def readme(data):
    projects = '\n\n'.join(f'### [{title}](https://github.com/{OWNER}/{repo})\n\n{description}\n\n{stack}<br>[Live preview]({demo}) · [Source code](https://github.com/{OWNER}/{repo})' for title, repo, description, stack, demo in PROJECTS)
    rows = '\n'.join(f'| {language} | {count} |' for language, count in data['languages'].items())
    return f'''<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/intro-dark-mobile.svg">
  <source media="(max-width: 600px)" srcset="assets/intro-light-mobile.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/intro-dark.svg">
  <img alt="Eraj Choriev — Frontend developer. React, Next.js and TypeScript." src="assets/intro-light.svg" width="100%">
</picture>

I build product interfaces, dashboards, and web experiences with **React, Next.js, and TypeScript**. My public work includes an EV charging station finder, an AI usage dashboard interface, and bilingual landing pages.

[Browse my projects](https://github.com/{OWNER}?tab=repositories) · [Recent public activity](https://github.com/{OWNER}?tab=overview)

## Selected projects

{projects}

## Development dashboard

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/dashboard-dark-mobile.svg">
  <source media="(max-width: 600px)" srcset="assets/dashboard-light-mobile.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/dashboard-dark.svg">
  <img alt="{data['projectCount']} public projects, {data['languageCount']} primary languages, {data['demoCount']} linked demos. {data['commitCount']} public default-branch commits across the displayed 12 weeks. Updated {data['periodEnd']}." src="assets/dashboard-light.svg" width="100%">
</picture>

Updated daily from public GitHub data. The chart counts commits attributed to this account on public project default branches; it is a different measure from the contribution calendar. [How the numbers are calculated](docs/METRICS.md).

<details>
<summary>View dashboard data as text</summary>

As of **{data['periodEnd']}**, Asia/Dushanbe: **{data['projectCount']}** public projects, **{data['demoCount']}** repositories with linked demos, **{data['commitCount']}** public default-branch commits from {data['periodStart']} to {data['periodEnd']}, across **{data['activeDays']}** active days.

| Primary language | Projects |
| :--- | ---: |
{rows}

[Public data snapshot](data/public.json) · [Automatic refresh](https://github.com/{OWNER}/{OWNER}/actions/workflows/profile.yml)

</details>

## Tools I work with

**Interfaces** — React, Next.js, TypeScript, JavaScript, HTML, CSS<br>
**Styling & motion** — Tailwind CSS, Framer Motion, Lucide<br>
**Data & visualization** — Firebase, Recharts, Python<br>
**Workflow** — Git, GitHub, Vite, Vercel

<sub>Every featured project links to source code and a live preview. Statistics use public repositories only.</sub>
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, help='Render an existing snapshot without network calls')
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text()) if args.snapshot else collect()
    for folder in ['assets', 'data']:
        (ROOT / folder).mkdir(exist_ok=True)
    for theme in THEMES:
        hero(theme)
        hero(theme, mobile=True)
        dashboard(data, theme)
        dashboard(data, theme, mobile=True)
    (ROOT / 'README.md').write_text(readme(data))
    (ROOT / 'data/public.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: data[k] for k in ['projectCount', 'languageCount', 'demoCount', 'commitCount', 'activeDays', 'periodStart', 'periodEnd']}))


if __name__ == '__main__':
    main()
