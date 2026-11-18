
import json
import hashlib
import datetime
import io
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ASSETS = DOCS / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)

FEEDS = [
    'https://morning-foot.com/feed/',
    'https://www.morning-foot.com/feed/'
]

S = requests.Session()
S.headers.update({
    'User-Agent': 'Mozilla/5.0 (compatible; MorningFootSocialStudio/2.0; +https://morning-foot.com)',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
})


def get(url):
    try:
        r = S.get(url, timeout=25)
        r.raise_for_status()
        return r
    except requests.RequestException as exc:
        print('FETCH ERROR:', url, exc)
        return None


def get_feed():
    for url in FEEDS:
        r = get(url)
        if r is None:
            continue

        feed = feedparser.parse(r.content)

        if feed.entries:
            print('RSS OK:', r.url, 'entries:', len(feed.entries))
            return feed

        print(
            'RSS invalid:', r.url,
            'type:', r.headers.get('Content-Type'),
            'preview:', r.text[:120]
        )

    raise SystemExit(
        'Aucun flux RSS exploitable. Verifier la protection '
        'du site pour GitHub Actions; anciens brouillons conserves.'
    )


def txt(s):
    return ' '.join(
        BeautifulSoup(s or '', 'html.parser').stripped_strings
    )


def category(t):
    s = t.lower()

    if any(x in s for x in [
        'datascout', 'statistique', 'chiffre',
        'classement', 'record', 'performance'
    ]):
        return 'STATS'

    if any(x in s for x in [
        'mercato', 'transfert', 'recrut',
        'prolong', 'contrat'
    ]):
        return 'MERCATO'

    if any(x in s for x in [
        'match', 'victoire', 'défaite',
        'but', 'ligue 1', 'ligue 2'
    ]):
        return 'MATCH'

    return 'DÉBAT'


def image_candidates(soup):
    body = soup.select_one(
        '.entry-content, .post-content, article .content, '
        '.et_pb_post .entry-content, article'
    ) or soup

    for img in body.select('img'):
        src = (
            img.get('data-src')
            or img.get('data-lazy-src')
            or img.get('src')
            or ''
        )

        if src and not src.startswith('data:'):
            yield urljoin('https://morning-foot.com', src), img


def save_image(url, stem):
    r = get(url)

    if r is None:
        return None

    try:
        im = Image.open(io.BytesIO(r.content))
        im.load()

        if im.width < 320 or im.height < 240:
            return None

        im.thumbnail((1500, 1900))

        out = ASSETS / (stem + '.jpg')

        im.convert('RGB').save(
            out,
            quality=86,
            optimize=True
        )

        return 'assets/' + out.name

    except Exception as exc:
        print('IMAGE ERROR:', url, exc)
        return None


def parse(entry):
    url = entry.get('link', '')
    ident = hashlib.sha1(url.encode()).hexdigest()[:14]
    title = txt(entry.get('title', ''))

    page = get(url)

    soup = (
        BeautifulSoup(page.text, 'html.parser')
        if page is not None
        else BeautifulSoup('', 'html.parser')
    )

    article = soup.select_one(
        '.entry-content, .post-content, article .content, '
        '.et_pb_post .entry-content, article'
    ) or soup

    text = txt(str(article))[:5000]

    reports = []

    for src, tag in image_candidates(soup):
        desc = (src + ' ' + tag.get('alt', '')).lower()

        if re.search(
            r'(report[-_]|datascout|fiche[-_])',
            desc
        ):
            reports.append(src)

    report = reports[0] if reports else None

    image = (
        save_image(report, ident + '-report')
        if report else None
    )

    c = category(title + ' ' + text[:450])

    score = 0
    reasons = []

    if image:
        score += 35
        reasons.append('Fiche statistique')

    if c == 'STATS':
        score += 20
        reasons.append('Statistiques')

    if c == 'MERCATO':
        score += 14
        reasons.append('Mercato')

    if any(k in title.lower() for k in [
        'psg', 'asse', 'marseille', 'lens',
        'lyon', 'griezmann', 'mbappé',
        'nantes', 'lille', 'monaco'
    ]):
        score += 15
        reasons.append('Sujet populaire')

    if any(k in title.lower() for k in [
        '?', 'record', 'incroyable',
        'révélation', 'surprise', 'explose',
        'pourquoi', 'combien'
    ]):
        score += 12
        reasons.append('Angle de discussion')

    if image:
        score += 8

    score = min(
        100,
        score + min(10, max(0, len(text) // 350))
    )

    date = (
        entry.get('published_parsed')
        or entry.get('updated_parsed')
    )

    day = (
        datetime.date(*date[:3]).isoformat()
        if date
        else datetime.date.today().isoformat()
    )

    question = {
        'STATS': 'Quel chiffre vous impressionne le plus ?',
        'MERCATO': 'Ce serait une bonne opération selon vous ?',
        'MATCH': 'Vous partagez cette analyse ?',
        'DÉBAT': 'Vous êtes d’accord ?'
    }[c]

    caption = (
        f'{title.rstrip(" .!?")}\n\n'
        'Une analyse à découvrir sur Morning Foot.\n\n'
        f'💬 {question}\n\n'
        'Article complet sur Morning-Foot.com — lien en bio.'
    )

    return {
        'id': ident,
        'title': title,
        'url': url,
        'date': day,
        'category': c,
        'score': score,
        'reasons': reasons,
        'report': bool(image),
        'image': image,
        'caption': caption,
        'question': question,
        'status': 'brouillon'
    }


def main():
    feed = get_feed()

    p = DOCS / 'posts.json'
    previous = []

    if p.exists():
        try:
            previous = json.loads(
                p.read_text(encoding='utf8')
            )
        except (ValueError, OSError) as exc:
            raise SystemExit(
                f'posts.json illisible, conservation du fichier: {exc}'
            )

    byurl = {
        item['url']: item
        for item in previous
        if item.get('url')
    }

    for entry in feed.entries[:25]:
        url = entry.get('link')

        if url and url not in byurl:
            try:
                byurl[url] = parse(entry)
            except Exception as exc:
                print('ARTICLE ERROR:', url, exc)

    items = sorted(
        byurl.values(),
        key=lambda x: (
            x.get('score', 0),
            x.get('date', '')
        ),
        reverse=True
    )[:120]

    recent = sorted(
        items,
        key=lambda x: x.get('date', ''),
        reverse=True
    )[:35]

    eligible = sorted(
        (
            x for x in recent
            if x.get('report') and x.get('image')
        ),
        key=lambda x: x.get('score', 0),
        reverse=True
    )

    chosen = {
        x['id']
        for x in eligible[:7]
        if x.get('score', 0) >= 35
    }

    for item in items:
        item['selected'] = item['id'] in chosen

    p.write_text(
        json.dumps(
            items,
            ensure_ascii=False,
            indent=2
        ),
        encoding='utf8'
    )

    print(
        'Posts:', len(items),
        'Selectionnes:', len(chosen)
    )


if __name__ == '__main__':
    main()
