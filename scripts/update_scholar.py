"""One direct public request; fail closed, retaining the last verified snapshot."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

URL = 'https://scholar.google.com/citations?user=TGyPrycAAAAJ&hl=en'

class Profile(HTMLParser):
    def __init__(self):
        super().__init__()
        self.name = ''
        self.counts = []
        self.homepage = False
        self.capture = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id') == 'gsc_prf_in':
            self.capture = 'name'
        elif tag == 'td' and 'gsc_rsb_std' in a.get('class', '').split():
            self.capture = 'count'
        if tag == 'a' and a.get('href', '').rstrip('/') == 'https://wuhao-me.github.io':
            self.homepage = True

    def handle_data(self, data):
        if self.capture == 'name':
            self.name += data
        elif self.capture == 'count':
            self.counts.append(data.strip())

    def handle_endtag(self, tag):
        if tag in ('div', 'td'):
            self.capture = None

def parse_count(html):
    if re.search(r'unusual traffic|recaptcha|/sorry/', html, re.I):
        raise ValueError('Scholar blocking page; no retry or bypass')
    p = Profile()
    p.feed(html)
    if p.name.strip().casefold() != 'hao wu' or not p.homepage:
        raise ValueError('Profile identity could not be verified')
    if not p.counts or not re.fullmatch(r'[0-9]+(?:,[0-9]{3})*', p.counts[0]):
        raise ValueError('Citation table missing or invalid')
    return int(p.counts[0].replace(',', ''))

def update(path, html, timestamp):
    count = parse_count(html)
    text = path.read_text(encoding='utf-8')
    replacement = (f'<!-- scholar-stats:start -->\n'
        f'              <p style="text-align:center;font-size:14px;color:#667085">'
        f'<a href="{URL}" target="_blank" rel="noopener noreferrer">Google Scholar citations: '
        f'<strong>{count:,}</strong></a><br>Last successful refresh: '
        f'<time datetime="{timestamp}">{timestamp.replace("T", " ").replace("Z", " UTC")}</time>'
        f' �� Refresh attempted daily; cached count.</p>\n'
        f'              <!-- scholar-stats:end -->')
    text, n = re.subn(r'<!-- scholar-stats:start -->.*?<!-- scholar-stats:end -->', replacement, text, flags=re.S)
    if n != 1:
        raise ValueError('Expected exactly one citation display')
    path.write_text(text, encoding='utf-8', newline='')
    return count

if __name__ == '__main__':
    try:
        with urlopen(Request(URL, headers={'User-Agent': 'wuhao-me citation updater (public academic homepage)'}), timeout=30) as response:
            if response.geturl().split('/')[2] != 'scholar.google.com':
                raise ValueError('Unexpected redirect')
            html = response.read(2_000_000).decode('utf-8')
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        print('Verified citation count:', update(Path('index.html'), html, stamp))
    except Exception as exc:
        print(f'Refresh failed; previous count and timestamp retained: {exc}', file=sys.stderr)
        sys.exit(1)
