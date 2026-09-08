#!/usr/bin/env python3
import argparse
import os
import re
import sys
import time
import urllib.parse
from datetime import date
import requests
from bs4 import BeautifulSoup
try:
    from rich.console import Console
    from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
    from rich.table import Table
    RICH = True
except Exception:
    RICH = False
BASE_URL = 'https://www.bbc.co.uk/learningenglish'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.9'}
RECENT_YEARS_ARCHIVE = [date.today().year - i for i in range(5)]
LEGACY_ARCHIVE_URL = f'{BASE_URL}/english/features/6-minute-english'
Episode = dict
LinkMap = dict

def console():
    return Console(highlight=False)

def log(msg):
    if RICH:
        Console(highlight=False).print(msg)
    else:
        uni_stdout(msg)

def uni_stdout(s=''):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(s, flush=True)

def check_network(verbose=False):
    targets = [('主站|Main', 'https://www.bbc.co.uk/learningenglish/', True), ('下载站|Download', 'https://downloads.bbc.co.uk/learningenglish/', True)]
    ok = True
    if verbose:
        log('[cyan]== 网络连通性检测 ==[/cyan]')
    for name, url, critical in targets:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            status = r.status_code
            reach = '✔ 可访问' if status < 400 else f'异常(HTTP {status})'
            if name.startswith('下载站'):
                reach = '✔ 可访问' if status in (200, 403, 404) else f'异常(HTTP {status})'
        except Exception as e:
            reach = f'✗ 不可访问({type(e).__name__}: {str(e)[:60]})'
            if critical:
                ok = False
        if verbose:
            log(f'  - {name:<14} {reach}')
        if critical and ('✗ 不可访问' in reach or reach.startswith('异常')):
            ok = False
    return ok

def extract_code(url: str) -> str:
    m = re.search('/(?:ep-(\\d{6})|(\\d{6}))(?:/|$)', url.rstrip('/'))
    if m:
        return m.group(1) or m.group(2)
    m2 = re.search('(\\d{6})', url)
    return m2.group(1) if m2 else url.rsplit('/', 1)[-1]

def fetch_year_episodes(year: int, session: requests.Session) -> list:
    url = f'{BASE_URL}/english/features/6-minute-english_{year}'
    out = []
    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return out
        soup = BeautifulSoup(r.text, 'html.parser')
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if f'6-minute-english_{year}' not in href:
                continue
            m = re.search('/(?:ep-)?(\\d{6})(?:/|$)', href)
            if not m:
                continue
            code = m.group(1)
            title = a.get_text(' ', strip=True)
            if not title or code in seen:
                continue
            seen.add(code)
            out.append(Episode(code=code, title=title, url=f'https://www.bbc.co.uk{href}' if href.startswith('/') else href))
        return out
    except Exception as e:
        log(f'[yellow]  - 年份 {year} 抓取失败: {type(e).__name__}: {str(e)[:60]}[/yellow]')
        return out

def fetch_legacy_episodes(session: requests.Session) -> list:
    out = []
    try:
        r = session.get(LEGACY_ARCHIVE_URL, headers=HEADERS, timeout=40)
        if r.status_code != 200:
            return out
        soup = BeautifulSoup(r.text, 'html.parser')
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if not re.search('6-minute-english/ep-\\d{6}', href):
                continue
            code = re.search('ep-(\\d{6})', href).group(1)
            title = a.get_text(' ', strip=True)
            if not title or code in seen:
                continue
            seen.add(code)
            out.append(Episode(code=code, title=title, url=f'https://www.bbc.co.uk{href}' if href.startswith('/') else href))
        return out
    except Exception as e:
        log(f'[yellow]  - 老节目归档页抓取失败: {type(e).__name__}: {str(e)[:60]}[/yellow]')
        return out

def code_year(code: str) -> int:
    m = re.search('(\\d{2})\\d{2}\\d{2}$', str(code))
    if not m:
        return 0
    yy = int(m.group(1))
    return 2000 + yy if yy < 70 else 1900 + yy

def parse_year_range(raw) -> list:
    if raw is None:
        return []
    t = str(raw).strip().lower()
    if t in ('', 'a', 'all', '*'):
        return []
    years = set()
    for part in re.split('[,\\s，、;]+', t):
        if not part:
            continue
        if part in ('a', 'all', '*'):
            return []
        if '-' in part:
            lo, _, hi = part.partition('-')
            try:
                lo = int(lo)
                hi = int(hi) if hi else lo
            except ValueError:
                continue
            if lo > hi:
                lo, hi = (hi, lo)
            years.update(range(lo, hi + 1))
        else:
            cap = re.fullmatch('(\\d{4})(?:年)?', part)
            if cap:
                years.add(int(cap.group(1)))
    this_year = date.today().year
    return sorted((y for y in years if 2000 <= y <= this_year + 1))

def fetch_episodes_by_years(years: list, session: requests.Session) -> list:
    year_parts = [y for y in years if isinstance(y, int)]
    need_legacy = 'legacy' in years
    legacy_filter = set((y for y in year_parts if y <= 2021))
    if legacy_filter:
        need_legacy = True
    if not year_parts and (not need_legacy):
        return []
    desc = []
    if year_parts:
        desc.append(f'{min(year_parts)}-{max(year_parts)}')
    if need_legacy:
        desc.append(LEGACY_LABEL)
    log(f"[cyan]== 按指定范围检索: {' / '.join(desc)} ==[/cyan]")
    all_eps: dict = {}
    for y in year_parts:
        eps = fetch_year_episodes(y, session)
        log(f'  - {y} 年归档: {len(eps)} 条')
        for ep in eps:
            all_eps.setdefault(ep['code'], ep)
    if need_legacy:
        legacy = fetch_legacy_episodes(session)
        if legacy_filter:
            legacy = [ep for ep in legacy if code_year(ep['code']) in legacy_filter]
        log(f'  - {LEGACY_LABEL}: {len(legacy)} 条')
        for ep in legacy:
            all_eps.setdefault(ep['code'], ep)
    eps = sorted(all_eps.values(), key=lambda e: e['code'], reverse=True)
    log(f'[green]== 符合范围共 {len(eps)} 条广播节目 ==[/green]')
    return eps

def fetch_all_episodes(session: requests.Session) -> list:
    log('[cyan]== 检索 6 Minute English 广播节目 ... ==[/cyan]')
    all_eps: dict = {}

    def _merge(items):
        for ep in items:
            all_eps.setdefault(ep['code'], ep)
    for y in RECENT_YEARS_ARCHIVE:
        eps = fetch_year_episodes(y, session)
        log(f'  - {y} 年归档: {len(eps)} 条')
        _merge(eps)
    legacy = fetch_legacy_episodes(session)
    log(f'  - 老节目归档(无年份页): {len(legacy)} 条')
    _merge(legacy)
    eps = sorted(all_eps.values(), key=lambda e: e['code'], reverse=True)
    log(f'[green]== 共检索到 {len(eps)} 条广播节目 ==[/green]')
    return eps

def prettify_title(title: str) -> str:
    t = re.sub('[\\\\/:*?\\"<>|]', '', title)
    t = re.sub('\\s+', '_', t.strip())
    return t or 'episode'

def print_page(eps: list, page: int, page_size: int):
    total_pages = max(1, (len(eps) + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = min(start + page_size, len(eps))
    log('')
    log(f'[bold]第 {page}/{total_pages} 页，共 {len(eps)} 条广播[/bold](p/n 翻页，q 退出)')
    if RICH:
        table = Table(show_header=True, header_style='bold cyan', box=None)
        table.add_column('位置', justify='right', width=5)
        table.add_column('节目代码', width=8)
        table.add_column('日期', width=10)
        table.add_column('标题')
        for i in range(start, end):
            ep = eps[i]
            table.add_row(str(i + 1), ep['code'], code_to_date(str(ep['code']).replace('ep-', '')), ep['title'])
        Console(highlight=False).print(table)
    else:
        for i in range(start, end):
            ep = eps[i]
            d = code_to_date(str(ep['code']).replace('ep-', ''))
            uni_stdout(f"{i + 1:>5}  {ep['code']}  {d}  {ep['title']}")

def parse_selection(text: str, total: int) -> list:
    t = text.strip().lower()
    if t in ('a', 'all', '*'):
        return list(range(1, total + 1))
    idxs = set()
    for part in re.split('[,\\s，、]+', t):
        if not part:
            continue
        if '-' in part:
            lo, _, hi = part.partition('-')
            lo = int(lo) if lo else 1
            hi = int(hi) if hi else total
            idxs.update(range(lo, hi + 1))
        else:
            try:
                idxs.add(int(part))
            except ValueError:
                continue
    return sorted((i for i in idxs if 1 <= i <= total))

def show_chosen(chosen: list):
    uni_stdout('=' * 60)
    uni_stdout(f'当前已选择 {len(chosen)} 期广播：')
    for ep in chosen[:5]:
        uni_stdout(f"    {ep['code']}  {ep['title']}")
    if len(chosen) > 5:
        uni_stdout(f'    ... 等共 {len(chosen)} 条')
    uni_stdout('=' * 60)

def select_episodes_text(eps: list, page_size: int) -> list:
    if not eps:
        return []
    page = 1
    total_pages = max(1, (len(eps) + page_size - 1) // page_size)
    chosen = []
    confirm = False
    while True:
        if not confirm:
            print_page(eps, page, page_size)
            uni_stdout('-' * 60)
            uni_stdout('输入节目序号(支持输入单个序号，如1,3/范围序号，如 2-6)a=全选，或 p/n 翻页、q 退出：')
            raw = input('> ').strip()
            low = raw.lower()
            if low == 'q':
                break
            if low == 'p':
                page = max(1, page - 1)
                continue
            if low == 'n':
                page = min(total_pages, page + 1)
                continue
            idxs = parse_selection(raw, len(eps))
            if not idxs:
                uni_stdout('[!] 无法识别的输入，请重试')
                continue
            for i in idxs:
                ep = eps[i - 1]
                if ep not in chosen:
                    chosen.append(ep)
            uni_stdout(f'[+] 已选择 {len(chosen)} 条')
            confirm = True
        else:
            show_chosen(chosen)
            uni_stdout('请确认：Y 确定下载 / N 返回继续选择 / C 清空重选 / Q 取消退出')
            ans = input('> ').strip().lower()
            if not ans:
                uni_stdout('[!] 请输入 Y / N / C / Q')
                continue
            c = ans[0]
            if c == 'y':
                return chosen
            elif c == 'n':
                confirm = False
            elif c == 'c':
                chosen = []
                confirm = False
            elif c == 'q':
                return []
            else:
                uni_stdout('[!] 无法识别的输入，请重试')
    return []

def _read_key() -> str:
    if sys.platform == 'win32':
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', 'à'):
            ch2 = msvcrt.getwch()
            return {'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right', 'I': 'pgup', 'Q': 'pgdn'}.get(ch2, '')
        if ch in ('\r', '\n'):
            return 'enter'
        if ch == ' ':
            return 'space'
        if ch in ('\x1b',):
            return 'esc'
        if ch == '\x03':
            raise KeyboardInterrupt
        return ch.lower()
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                seq = sys.stdin.read(2)
                return {'[A': 'up', '[B': 'down', '[C': 'right', '[D': 'left', '[5~': 'pgup', '[6~': 'pgdn'}.get(seq, 'esc')
            if ch in ('\r', '\n'):
                return 'enter'
            if ch == ' ':
                return 'space'
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

def _clear_screen():
    if sys.platform == 'win32':
        os.system('cls')
    else:
        uni_stdout('\x1b[2J\x1b[H')

def code_to_date(code: str) -> str:
    if not code:
        return ''
    m = re.match('^(\\d{2})(\\d{2})(\\d{2})$', code)
    if not m:
        return ''
    yy, mm, dd = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    yyyy = 2000 + yy if yy < 70 else 1900 + yy
    try:
        import datetime
        d = datetime.date(yyyy, mm, dd)
    except (ValueError, TypeError):
        return ''
    return d.strftime('%Y-%m-%d')

def select_episodes_tui(eps: list, page_size: int) -> list:
    total = len(eps)
    if total == 0:
        return []
    total_pages = max(1, (total + page_size - 1) // page_size)
    state = {'page': 1, 'cursor': 0, 'sel': set()}

    def page_items() -> list:
        start = (state['page'] - 1) * page_size
        return list(range(start, min(start + page_size, total)))

    def render() -> str:
        items = page_items()
        cur_sel = set(items) & state['sel']
        page_all = bool(items) and len(cur_sel) == len(items)
        all_all = len(state['sel']) == total

        def box(on: bool) -> str:
            return '[✔]' if on else '[ ]'
        lines = []
        lines.append('  BBC Learning English - 6 Minute English 下载器')
        lines.append('  ' + '=' * 74)
        lines.append(f"  共 {total} 期广播 | 第 {state['page']}/{total_pages} 页 | 已选 {len(state['sel'])} 期")
        lines.append('  ' + '-' * 74)
        lines.append(('  >> ' if state['cursor'] == 0 else '     ') + box(page_all) + f' 全选当前页({len(items)} 期)')
        lines.append(('  >> ' if state['cursor'] == 1 else '     ') + box(all_all) + f' 全选全部页面({total} 期)')
        lines.append('  ' + '-' * 74)
        for k, gidx in enumerate(items):
            row = k + 2
            ep = eps[gidx]
            on = gidx in state['sel']
            mark = box(on)
            cur = '>>' if state['cursor'] == row else '  '
            code_s = str(ep.get('code', '')).replace('ep-', '')
            date_part = code_to_date(code_s)
            if date_part:
                line = f"{cur} {mark} {code_s}  {date_part}  {ep['title']}"
            else:
                line = f"{cur} {mark} {code_s:<10}  {ep['title']}"
            lines.append(line)
        lines.append('  ' + '-' * 74)
        lines.append('  ↑/↓ 移动  Space 勾选  ←/→ 翻页  Enter 确认  Q 取消')
        return '\n'.join(lines)

    def toggle():
        items = page_items()
        if state['cursor'] == 0:
            cur_sel = set(items) & state['sel']
            if items and len(cur_sel) == len(items):
                state['sel'] -= set(items)
            else:
                state['sel'] |= set(items)
        elif state['cursor'] == 1:
            if len(state['sel']) == total:
                state['sel'].clear()
            else:
                state['sel'] = set(range(total))
        else:
            k = state['cursor'] - 2
            if 0 <= k < len(items):
                gidx = items[k]
                if gidx in state['sel']:
                    state['sel'].discard(gidx)
                else:
                    state['sel'].add(gidx)
    try:
        while True:
            _clear_screen()
            uni_stdout(render())
            key = _read_key()
            if key == 'up':
                if state['cursor'] > 0:
                    state['cursor'] -= 1
            elif key == 'down':
                if state['cursor'] < 2 + len(page_items()) - 1:
                    state['cursor'] += 1
            elif key == 'left':
                state['page'] = max(1, state['page'] - 1)
            elif key == 'right':
                state['page'] = min(total_pages, state['page'] + 1)
            elif key == 'pgup':
                state['page'] = 1
            elif key == 'pgdn':
                state['page'] = total_pages
            elif key == 'space':
                toggle()
            elif key == 'enter':
                break
            elif key in ('q', 'esc'):
                return []
    except KeyboardInterrupt:
        return []
    finally:
        _clear_screen()
    return [eps[i] for i in sorted(state['sel'])]

def select_episodes(eps: list, page_size: int) -> list:
    if not eps:
        return []
    if sys.stdin.isatty():
        try:
            return select_episodes_tui(eps, page_size)
        except Exception as e:
            uni_stdout(f'[!] TUI 启动失败({type(e).__name__}: {e})，降级为文本模式')
    return select_episodes_text(eps, page_size)

def select_years(options: list):
    if not options:
        return []
    values = [v for v, _ in options]
    if not sys.stdin.isatty():
        while True:
            uni_stdout('可用选项: ' + ', '.join((str(v) for v in values)))
            uni_stdout('输入年份(直接回车=全量；支持区间如 2022-2024 / 2020-2021 表示老节目)：')
            raw = input('> ').strip()
            if not raw:
                return []
            picked = []
            yset = set((v for v in values if isinstance(v, int)))
            for y in parse_year_range(raw):
                if y in yset:
                    picked.append(y)
            if raw.lower() in ('legacy', '老', 'old') or _has_old_range(parse_year_range(raw)):
                picked.append('legacy')
            if picked:
                return [v for v in values if v in picked]
            uni_stdout(f'[!] 无匹配选项: {raw!r}，请重试')
    total = len(options)
    state = {'cursor': 0, 'sel': set()}

    def render() -> str:
        all_on = len(state['sel']) == total

        def box(on: bool) -> str:
            return '[✔]' if on else '[ ]'
        lines = []
        lines.append('  选择检索范围')
        lines.append('  ' + '=' * 60)
        lines.append(f"  共 {total} 个选项 | 已选 {len(state['sel'])} 项 | 空选回车=全量")
        lines.append('  ' + '-' * 60)
        lines.append(('  >> ' if state['cursor'] == 0 else '     ') + box(all_on) + f' 全选全部({total} 项)')
        lines.append('  ' + '-' * 60)
        for k, (v, label) in enumerate(options):
            row = k + 1
            mark = box(v in state['sel'])
            cur = '>>' if state['cursor'] == row else '  '
            lines.append(f'{cur} {mark} {label}')
        lines.append('  ' + '-' * 60)
        lines.append('  ↑/↓ 移动  Space 勾选  Enter 确认  Q 取消')
        return '\n'.join(lines)

    def toggle():
        if state['cursor'] == 0:
            if len(state['sel']) == total:
                state['sel'].clear()
            else:
                state['sel'] = set(values)
        else:
            k = state['cursor'] - 1
            if 0 <= k < total:
                v = values[k]
                if v in state['sel']:
                    state['sel'].discard(v)
                else:
                    state['sel'].add(v)
    try:
        while True:
            _clear_screen()
            uni_stdout(render())
            key = _read_key()
            if key == 'up':
                state['cursor'] = max(0, state['cursor'] - 1)
            elif key == 'down':
                state['cursor'] = min(total, state['cursor'] + 1)
            elif key == 'space':
                toggle()
            elif key == 'enter':
                break
            elif key in ('q', 'esc'):
                return None
    except KeyboardInterrupt:
        return None
    finally:
        _clear_screen()
    return [v for v in values if v in state['sel']]
LEGACY_LABEL = '老节目(2021年及以前)'

def _has_old_range(years: list) -> bool:
    return any((y <= 2021 for y in years))

def ask_year_scope() -> list:
    this_year = date.today().year
    options = [(y, f'{y} 年') for y in range(this_year, 2021, -1)]
    options.append(('legacy', LEGACY_LABEL))
    uni_stdout('')
    uni_stdout('选择检索范围 (可多选，方向键+空格勾选)：')
    return select_years(options)

def ask_download_path() -> str:
    default_dir = os.path.join(os.path.expanduser('~'), 'Downloads', '6MinuteEnglish')
    uni_stdout('')
    uni_stdout('请输入下载保存目录：')
    uni_stdout(f'(若直接回车将使用默认目录: {default_dir})')
    raw = input('> ').strip().strip('"').strip("'")
    if not raw:
        p = default_dir
    else:
        if raw.startswith('~'):
            raw = os.path.expanduser(raw)
        p = os.path.abspath(raw)
    os.makedirs(p, exist_ok=True)
    log(f'[green]下载目录: {p}[/green]')
    return p

def sanitize_filename(name: str) -> str:
    name = urllib.parse.unquote(name)
    name = name.replace(' ', '_')
    name = re.sub('[\\\\/:*?\\"<>|%]', '_', name)
    return name.strip('_. ')

def parse_download_links(ep: Episode, session: requests.Session) -> LinkMap:
    links = {'pdf': None, 'audio': None, 'transcript': None}
    try:
        r = session.get(ep['url'], headers=HEADERS, timeout=30)
        if r.status_code != 200:
            log(f"[red] ✗ {ep['code']} 页面打开失败 HTTP {r.status_code}[/red]")
            return links
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        log(f"[red] ✗ {ep['code']} 页面打开异常: {type(e).__name__}[/red]")
        return links
    anchors = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not (href.startswith('http') or href.startswith('/')):
            continue
        full = href if href.startswith('http') else f'https://www.bbc.co.uk{href}'
        anchors.append((a.get_text(' ', strip=True).strip().lower(), full))
    for text, href in anchors:
        low = href.lower()
        if links['pdf'] is None and text == 'download pdf' and low.endswith('.pdf'):
            links['pdf'] = href
        if links['audio'] is None and text == 'download audio' and low.endswith('.mp3'):
            links['audio'] = href
        if links['transcript'] is None and 'transcript' in text and low.endswith('.pdf'):
            links['transcript'] = href
    if links['pdf'] is None:
        cands = [h for _, h in anchors if 'worksheet' in h.lower() and h.lower().endswith('.pdf')]
        links['pdf'] = cands[0] if cands else None
    if links['transcript'] is None:
        cands = [h for _, h in anchors if 'transcript' in h.lower() and h.lower().endswith('.pdf')]
        links['transcript'] = cands[0] if cands else None
    if links['transcript'] is None and links['pdf'] and 'worksheet' not in links['pdf'].lower():
        links['transcript'] = links['pdf']
    heads = session.head
    if links['pdf'] is None and links['audio'] is None and (links['transcript'] is None):
        base = f"https://downloads.bbc.co.uk/learningenglish/features/6min/{ep['code']}_6_minute_english_{prettify_title(ep['title'])}"
        guesses = {'pdf': f'{base}_worksheet_.pdf', 'audio': f'{base}_download.mp3', 'transcript': f'{base}_transcript.pdf'}
        for key, g in guesses.items():
            try:
                hr = heads(g, headers=HEADERS, timeout=15, allow_redirects=True)
                if hr.status_code == 200:
                    links[key] = g
            except Exception:
                pass
    return links

def download_file(url: str, dest: str, session: requests.Session, timeout=60, retries=2) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        log(f'        [dim]已存在，跳过: {os.path.basename(dest)}[/dim]')
        return True
    tmp = dest + '.part'
    headers = {**HEADERS}
    resume_pos = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    if resume_pos:
        headers['Range'] = f'bytes={resume_pos}-'
    for attempt in range(1, retries + 2):
        try:
            with session.get(url, headers=headers, timeout=timeout, stream=True) as r:
                if r.status_code == 200:
                    mode = 'ab' if resume_pos else 'wb'
                elif r.status_code == 206:
                    mode = 'ab'
                elif r.status_code == 404:
                    log(f'        [red]✗ 资源不存在(404): {url}[/red]')
                    return False
                else:
                    raise requests.HTTPError(f'HTTP {r.status_code}')
                total = int(r.headers.get('Content-Length', 0)) + (resume_pos if resume_pos else 0)
                with open(tmp, mode) as f:
                    downloaded = resume_pos
                    if RICH and sys.stdout.isatty() and total:
                        with Progress(TextColumn('[progress.description]{task.description}'), BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(), console=Console(highlight=False)) as p:
                            task = p.add_task(description=os.path.basename(dest), total=total)
                            for chunk in r.iter_content(chunk_size=1 << 16):
                                if not chunk:
                                    continue
                                f.write(chunk)
                                downloaded += len(chunk)
                                p.update(task, completed=downloaded)
                    else:
                        for chunk in r.iter_content(chunk_size=1 << 16):
                            if not chunk:
                                continue
                            f.write(chunk)
                            downloaded += len(chunk)
                os.replace(tmp, dest)
                return True
        except (requests.RequestException, requests.HTTPError, OSError) as e:
            resume_pos = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            if attempt <= retries:
                log(f'        [yellow]⚠ 下载失败({type(e).__name__})，重试 {attempt}/{retries} ...[/yellow]')
                time.sleep(1.5 * attempt)
            else:
                log(f'        [red]✗ 下载失败: {url}[/red]  [{type(e).__name__}: {str(e)[:50]}]')
    return False

def download_episode(ep: Episode, out_root: str, session: requests.Session) -> dict:
    folder = os.path.join(out_root, f"{ep['code']}_{prettify_title(ep['title'])}")
    os.makedirs(folder, exist_ok=True)
    log(f"[cyan]== 处理 {ep['code']} - {ep['title']} ==[/cyan]")
    links = parse_download_links(ep, session)
    result = {'code': ep['code'], 'title': ep['title'], 'folder': folder, 'files': []}
    labels = {'pdf': 'Download PDF', 'audio': 'Download Audio', 'transcript': 'Download Transcript'}
    for key, label in labels.items():
        url = links[key]
        if not url:
            log(f'    [yellow]- {label}: 页面未找到该链接[/yellow]')
            continue
        fname = sanitize_filename(os.path.basename(url.split('?')[0]))
        dest = os.path.join(folder, fname)
        log(f'    - {label}: {url}')
        if download_file(url, dest, session):
            result['files'].append(dest)
    time.sleep(0.3)
    return result

def summarize(results: list):
    log('')
    log('[bold green]== 下载汇总 ==[/bold green]')
    ok_total = fail_total = 0
    for res in results:
        n = len(res['files'])
        log(f"  {res['code']}  {res['title']}   -> {n} 个文件")
        for f in res['files']:
            size = os.path.getsize(f) if os.path.exists(f) else 0
            log(f'      [✔] {os.path.basename(f)}  ({size / 1024:.1f} KB)')
        ok_total += n
    log(f'[green]✔ 共下载 {ok_total} 个文件，保存目录见上方；每期一个独立文件夹[/green]')

def main():
    ap = argparse.ArgumentParser(description='BBC Learning English 6 Minute English 下载器', add_help=True)
    ap.add_argument('--check', action='store_true', help='仅执行网络环境检测后退出')
    ap.add_argument('--year', default=None, help='只检索指定年份或年份范围，如 2024 / 2019-2024 / 2015,2018,2020-2022；不指定时交互询问年份范围(回车=全量)')
    ap.add_argument('--out', default=None, help='下载保存根目录(不指定时交互确认，回车默认 Downloads/6MinuteEnglish)')
    ap.add_argument('--page-size', type=int, default=20, help='分页每页条数(默认 20)')
    ap.add_argument('--limit', type=int, default=0, help='只处理最近 N 条(试跑用，0=全部)')
    args = ap.parse_args()
    uni_stdout('=' * 64)
    uni_stdout('  BBC Learning English - 6 Minute English 广播下载器')
    uni_stdout('=' * 64)
    ok = check_network(verbose=True)
    if not ok:
        log('[red]✗ 网站连通性检测不通过，请检查网络/代理后重试[/red]')
        sys.exit(1)
    if args.check:
        log('[green]✔ 网站连通性检测通过[/green]')
        return
    session = requests.Session()
    if args.year is not None:
        years = parse_year_range(args.year)
        if not years:
            log(f'[yellow]--year 参数 {args.year!r} 无法解析，回退为全量检索[/yellow]')
    else:
        years = ask_year_scope()
        if years is None:
            log('[yellow]已取消年份选择，退出[/yellow]')
            return
    if years:
        eps = fetch_episodes_by_years(years, session)
    else:
        eps = fetch_all_episodes(session)
    if not eps:
        log('[red]✗ 未检索到任何广播，退出[/red]')
        sys.exit(2)
    if args.limit:
        eps = eps[:args.limit]
        log(f'[dim]按 --limit {args.limit} 裁剪后共 {len(eps)} 条[/dim]')
    chosen = select_episodes(eps, args.page_size)
    if not chosen:
        log('[yellow]✗ 未选择任何节目，退出[/yellow]')
        return
    if args.out:
        out_root = os.path.abspath(os.path.expanduser(args.out))
        os.makedirs(out_root, exist_ok=True)
        log(f'[cyan]下载目录(通过 --out 指定): {out_root}[/cyan]')
    else:
        out_root = ask_download_path()
    log(f'[cyan]下载目录: {out_root}，共 {len(chosen)} 个节目 ...[/cyan]')
    results = [download_episode(ep, out_root, session) for ep in chosen]
    summarize(results)
    log('[green]全部完成[/green]')
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        uni_stdout('\n✗ 已取消（Ctrl+C），退出')
        sys.exit(130)