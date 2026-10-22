"""Update marked profile sections from public GitHub data, using stdlib only."""
import html
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

USER = os.environ.get('PROFILE_USER', 'RuomuAnshi')
README = Path(__file__).resolve().parents[1] / 'README.md'


def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'profile-updater'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    with urlopen(Request('https://api.github.com' + path, headers=headers), timeout=30) as response:
        return json.load(response)


def esc(value):
    return html.escape(str(value), quote=True)


def replace_section(text, name, content):
    start, end = f'<!-- {name}:START -->', f'<!-- {name}:END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f'Expected one marker pair for {name}')
    before, tail = text.split(start)
    _, after = tail.split(end)
    return before + start + '\n' + content + '\n' + end + after


def projects_html(repos):
    repos = [r for r in repos if not r.get('private') and not r.get('fork')
             and not r.get('archived') and r['name'].lower() != USER.lower()]
    repos.sort(key=lambda r: r.get('pushed_at') or '', reverse=True)
    rows = []
    for r in repos[:5]:
        rows.append(f'<li><a href="https://github.com/{esc(r["full_name"])}"><strong>{esc(r["name"])}</strong></a> — {esc(r.get("description") or "持续构建中。")}<br /><sub>{esc(r.get("language") or "Code")} · ★ {r["stargazers_count"]} · 最近推送 {esc((r.get("pushed_at") or "")[:10])}</sub></li>')
    return '<ul>\n' + '\n'.join(rows) + '\n</ul>' if rows else '<p>暂无公开项目。</p>'


def activity_html(events):
    rows = []
    labels = {'PushEvent': '推送代码', 'PullRequestEvent': '更新 PR',
              'IssuesEvent': '更新 Issue', 'ReleaseEvent': '发布版本',
              'CreateEvent': '创建仓库或分支', 'WatchEvent': '收藏项目', 'ForkEvent': 'Fork 项目'}
    for e in events:
        repo = e['repo']['name']
        if not e.get('public') or repo.lower() == f'{USER}/{USER}'.lower() or e['type'] not in labels:
            continue
        payload = e.get('payload', {})
        detail = payload.get('pull_request') or payload.get('issue') or payload.get('release') or {}
        url = detail.get('html_url') or 'https://github.com/' + repo
        if not url.startswith('https://github.com/'):
            url = 'https://github.com/' + repo
        rows.append(f'<li><sub>{esc(e["created_at"][:10])}</sub> · {labels[e["type"]]} · <a href="{esc(url)}">{esc(repo)}</a></li>')
        if len(rows) == 6:
            break
    return '<ul>\n' + '\n'.join(rows) + '\n</ul>' if rows else '<p>近期暂无公开动态。</p>'


def main():
    repos, page = [], 1
    while True:
        batch = api(f'/users/{USER}/repos?type=owner&sort=pushed&per_page=100&page={page}')
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    events = api(f'/users/{USER}/events/public?per_page=100')
    original = README.read_text()
    updated = replace_section(original, 'PROJECTS', projects_html(repos))
    updated = replace_section(updated, 'ACTIVITY', activity_html(events))
    # API failures occur before writing, preserving the previous profile.
    if updated != original:
        README.write_text(updated)
        print('Profile updated.')
    else:
        print('Profile content unchanged.')


if __name__ == '__main__':
    main()
