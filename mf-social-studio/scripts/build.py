
import json
import hashlib
import datetime
import io
import re
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
import feedparser
from bs4 import BeautifulSoup
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ASSETS = DOCS / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)

PARIS = ZoneInfo('Europe/Paris')

FEEDS = [
    'https://morning-foot.com/feed/',
    'https://www.morning-foot.com/feed/'
]

S = requests.Session()
S.headers.update({
    'User-Agent': 'Mozilla/5.0 (compatible; MorningFootSocialStudio/8.0; +https://morning-foot.com)',
    'Accept': '*/*'
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

        print('RSS invalid:', r.url)

    raise SystemExit(
        'Aucun flux RSS exploitable. Anciens brouillons conserves.'
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


def is_report(value):
    return bool(re.search(
        r'(report[-_]|datascout|fiche[-_])',
        str(value or ''),
        re.I
    ))


def image_candidates(soup, base_url):
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
            yield urljoin(base_url, src), img


def photo_candidates(soup, entry, base_url):
    candidates = []

    def add(value):
        if not isinstance(value, str):
            return

        value = value.strip()

        if not value or value.startswith('data:'):
            return

        value = urljoin(base_url, value)

        if not value.startswith(('https://', 'http://')):
            return

        if re.search(
            r'(datascout|report[-_]|fiche[-_]|logo|avatar|favicon|placeholder|gravatar)',
            value,
            re.I
        ):
            return

        if value not in candidates:
            candidates.append(value)

    for selector in [
        'meta[property="og:image"]',
        'meta[property="og:image:secure_url"]',
        'meta[name="twitter:image"]',
        'meta[property="twitter:image"]'
    ]:
        for tag in soup.select(selector):
            add(tag.get('content'))

    for tag in soup.select('link[rel="image_src"]'):
        add(tag.get('href'))

    for media in entry.get('media_content', []):
        add(media.get('url'))

    for media in entry.get('media_thumbnail', []):
        add(media.get('url'))

    for enclosure in entry.get('enclosures', []):
        if enclosure.get('type', '').startswith('image/'):
            add(enclosure.get('href') or enclosure.get('url'))

    for img in soup.select(
        'img.wp-post-image, '
        '.post-thumbnail img, '
        '.featured-image img, '
        '.et_post_meta_wrapper img'
    ):
        add(
            img.get('data-src')
            or img.get('data-lazy-src')
            or img.get('src')
        )

    return candidates


def save_image(url, stem, min_width=320):
    out = ASSETS / (stem + '.jpg')

    if out.exists():
        try:
            with Image.open(out) as existing:
                if existing.width >= min_width:
                    existing.verify()
                    return 'assets/' + out.name

        except Exception:
            pass

    r = get(url)

    if r is None:
        return None

    try:
        im = Image.open(io.BytesIO(r.content))
        im = ImageOps.exif_transpose(im)
        im.load()

        if im.width < min_width or im.height < 240:
            return None

        im.thumbnail((1600, 1900))

        im.convert('RGB').save(
            out,
            quality=88,
            optimize=True
        )

        return 'assets/' + out.name

    except Exception as exc:
        print('IMAGE ERROR:', url, exc)
        return None


def shorten(text, limit):
    text = text.strip()

    if len(text) <= limit:
        return text

    part = text[:limit]

    end = max(
        part.rfind('. '),
        part.rfind('! '),
        part.rfind('? ')
    )

    if end >= limit // 2:
        return part[:end + 1]

    return part.rsplit(' ', 1)[0] + '…'


def extract_intro(soup, entry, title):
    for selector in [
        '.entry-content',
        '.post-content',
        'article .content',
        '.et_pb_post .entry-content'
    ]:
        body = soup.select_one(selector)

        if body is None:
            continue

        for tag in body.select('p'):
            text = txt(str(tag))

            if len(text) >= 100:
                if text.lower().startswith((
                    'à lire aussi',
                    'a lire aussi',
                    'retrouvez-nous',
                    'abonnez-vous'
                )):
                    continue

                return shorten(text, 420)

    for selector in [
        'meta[property="og:description"]',
        'meta[name="description"]'
    ]:
        tag = soup.select_one(selector)

        if tag:
            text = txt(tag.get('content', ''))

            if len(text) >= 70:
                return shorten(text, 420)

    summary = txt(entry.get('summary', ''))

    if summary and summary != title:
        return shorten(summary, 420)

    return ''


def asset_exists(value):
    if not isinstance(value, str):
        return False

    if not value.startswith('assets/'):
        return False

    path = ASSETS / Path(value).name

    return path.is_file()


def parse(entry, old=None):
    old = old or {}

    url = entry.get('link', '')
    ident = hashlib.sha1(url.encode()).hexdigest()[:14]
    title = txt(entry.get('title', '')) or old.get('title', '')

    page = get(url)

    soup = (
        BeautifulSoup(page.text, 'html.parser')
        if page is not None
        else BeautifulSoup('', 'html.parser')
    )

    base_url = page.url if page is not None else url

    article = soup.select_one(
        '.entry-content, .post-content, article .content, '
        '.et_pb_post .entry-content, article'
    ) or soup

    text = txt(str(article))[:5000]

    # ----------------------------
    # PHOTO PRINCIPALE
    # ----------------------------

    photo = (
        old.get('cover_image')
        or old.get('photo')
    )

    if not asset_exists(photo):
        photo = None

        for src in photo_candidates(soup, entry, base_url):
            photo = save_image(
                src,
                ident + '-photo',
                min_width=500
            )

            if photo:
                print('PHOTO OK:', title, photo)
                break

    if not photo:
        print('PHOTO ABSENTE:', title)

    # ----------------------------
    # INFOGRAPHIE DATASCOUT
    # ----------------------------

    image = old.get('report_image') or old.get('image')

    if not asset_exists(image):
        image = None
        reports = []

        for src, tag in image_candidates(soup, base_url):
            desc = src + ' ' + str(tag.get('alt', ''))

            if is_report(desc):
                reports.append(src)

        if not reports:
            for content in entry.get('content', []):
                rss_soup = BeautifulSoup(
                    content.get('value', ''),
                    'html.parser'
                )

                for src, tag in image_candidates(rss_soup, base_url):
                    desc = src + ' ' + str(tag.get('alt', ''))

                    if is_report(desc):
                        reports.append(src)

        for report in reports[:5]:
            image = save_image(
                report,
                ident + '-report'
            )

            if image:
                break

    # ----------------------------
    # CATEGORIE ET SCORE
    # ----------------------------

    c = category(title + ' ' + text[:450])

    if page is None and old.get('category'):
        c = old['category']

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

    if photo:
        score += 5
        reasons.append('Photo disponible')

    score = min(
        100,
        score + min(10, max(0, len(text) // 350))
    )

    if page is None and old.get('score') is not None:
        score = old['score']

    # ----------------------------
    # DATE DE PUBLICATION
    # ----------------------------

    date = (
        entry.get('published_parsed')
        or entry.get('updated_parsed')
    )

    if date:
        published = datetime.datetime(
            *date[:6],
            tzinfo=datetime.timezone.utc
        ).astimezone(PARIS)

        day = published.date().isoformat()
        published_at = published.isoformat()

    else:
        day = (
            old.get('date')
            or datetime.datetime.now(PARIS).date().isoformat()
        )

        published_at = (
            old.get('published_at')
            or day + 'T00:00:00'
        )

    # ----------------------------
    # QUESTION ET LEGENDE
    # ----------------------------

    question = {
        'STATS': 'Que vous inspirent ces chiffres ?',
        'MERCATO': 'Que pensez-vous de cette actualité mercato ?',
        'MATCH': 'Quel est votre avis ?',
        'DÉBAT': 'Qu’en pensez-vous ?'
    }[c]

    intro = extract_intro(soup, entry, title)

    if not intro:
        intro = old.get('intro', '')

    parts = [title]

    if intro:
        parts.append(intro)

    if image:
        parts.append(
            '📊 Décryptage et statistiques avec les données DataScout.'
        )

    parts.append(f'💬 {question}')

    parts.append(
        '🔗 Article complet sur morning-foot.com — lien en bio.'
    )

    caption = '\n\n'.join(parts)

    # ----------------------------
    # DONNEES DU SOCIAL STUDIO
    # ----------------------------

    return {
        **old,
        'id': ident,
        'title': title,
        'url': url,
        'date': day,
        'published_at': published_at,
        'category': c,
        'score': score,
        'reasons': reasons,
        'report': bool(image),
        'image': image,
        'report_image': image,
        'photo': photo,
        'cover_image': photo,
        'intro': intro,
        'caption': caption,
        'question': question,
        'status': old.get('status', 'brouillon'),
        'build_version': 8
    }


# ========================================
# FRAICHEUR DES ARTICLES
# ========================================


def age_days(item):
    try:
        day = datetime.date.fromisoformat(
            item.get('date', '')
        )

        today = datetime.datetime.now(PARIS).date()

        return max(0, (today - day).days)

    except (ValueError, TypeError):
        return 999


def editorial_score(item):
    score = item.get('score', 0)
    age = age_days(item)

    freshness = {
        0: 30,
        1: 20,
        2: 10,
        3: 5
    }.get(age, 0)

    penalty = max(0, age - 3) * 5

    return score + freshness - penalty


def publication_key(item):
    return (
        item.get('published_at')
        or item.get('date', '')
    )


# ========================================
# GENERATION PRINCIPALE
# ========================================


def main():
    feed = get_feed()

    p = DOCS / 'posts.json'
    previous = []

    if p.exists():
        try:
            previous = json.loads(
                p.read_text(encoding='utf8')
            )

            if not isinstance(previous, list):
                raise ValueError('Format JSON invalide')

        except (ValueError, OSError) as exc:
            raise SystemExit(
                f'posts.json illisible: {exc}'
            )

    byurl = {
        item['url']: item
        for item in previous
        if item.get('url')
    }

    new_count = 0

    # ----------------------------
    # RECUPERATION DES ARTICLES
    # ----------------------------

    for entry in feed.entries[:30]:
        url = entry.get('link')

        if not url:
            continue

        old = byurl.get(url, {})

        needs_update = (
            not old
            or old.get('build_version') != 8
            or not asset_exists(old.get('cover_image'))
            or (
                old.get('report')
                and not asset_exists(old.get('image'))
            )
        )

        if needs_update:
            try:
                byurl[url] = parse(entry, old)

                if not old:
                    new_count += 1
                    print(
                        'NOUVEL ARTICLE:',
                        byurl[url].get('title')
                    )

            except Exception as exc:
                print('ARTICLE ERROR:', url, exc)

    # ----------------------------
    # RECUPERATION DES ANCIENNES
    # PHOTOS MANQUANTES
    # ----------------------------

    active_urls = {
        entry.get('link')
        for entry in feed.entries[:30]
    }

    old_selected = [
        item for item in byurl.values()
        if item.get('selected')
        and item['url'] not in active_urls
        and age_days(item) <= 6
        and not asset_exists(item.get('cover_image'))
    ]

    for old in old_selected[:7]:
        try:
            entry = {
                'link': old['url'],
                'title': old['title']
            }

            byurl[old['url']] = parse(entry, old)

        except Exception as exc:
            print('BACKFILL ERROR:', old['url'], exc)

    # ----------------------------
    # 120 ARTICLES LES PLUS RECENTS
    # ----------------------------

    items = sorted(
        byurl.values(),
        key=lambda x: (
            publication_key(x),
            x.get('score', 0)
        ),
        reverse=True
    )[:120]

    # ----------------------------
    # ARTICLES DATASCOUT ELIGIBLES
    # ----------------------------

    eligible = [
        x for x in items
        if x.get('report')
        and asset_exists(x.get('image'))
        and age_days(x) <= 6
        and x.get('score', 0) >= 35
    ]

    # Priorite absolue :
    # articles du jour et de la veille

    fresh = sorted(
        (
            x for x in eligible
            if age_days(x) <= 1
        ),
        key=lambda x: (
            editorial_score(x),
            publication_key(x)
        ),
        reverse=True
    )

    # Complement :
    # articles des jours precedents

    older = sorted(
        (
            x for x in eligible
            if 2 <= age_days(x) <= 6
        ),
        key=lambda x: (
            editorial_score(x),
            publication_key(x)
        ),
        reverse=True
    )

    selected = (fresh + older)[:7]

    chosen = {
        x['id']
        for x in selected
    }

    ranks = {
        x['id']: index + 1
        for index, x in enumerate(selected)
    }

    # ----------------------------
    # METADONNEES DE SYNCHRONISATION
    # ----------------------------

    now = datetime.datetime.now(PARIS)

    sync_time = now.isoformat(
        timespec='seconds'
    )

    sync_label = now.strftime(
        '%d/%m/%Y à %H:%M'
    )

    for item in items:
        item['selected'] = item['id'] in chosen

        item['selection_rank'] = ranks.get(
            item['id'],
            None
        )

        item['editorial_score'] = editorial_score(item)

        item['age_days'] = age_days(item)

        item['last_sync'] = sync_time

        item['last_sync_label'] = sync_label

    # ----------------------------
    # ECRITURE ATOMIQUE DU JSON
    # ----------------------------

    temp = DOCS / 'posts.json.tmp'

    temp.write_text(
        json.dumps(
            items,
            ensure_ascii=False,
            indent=2
        ),
        encoding='utf8'
    )

    temp.replace(p)

    # ----------------------------
    # BILAN DE LA SYNCHRONISATION
    # ----------------------------

    photo_count = sum(
        asset_exists(x.get('cover_image'))
        for x in items
    )

    report_count = sum(
        asset_exists(x.get('image'))
        for x in items
    )

    today_count = sum(
        age_days(x) == 0
        for x in items
    )

    yesterday_count = sum(
        age_days(x) == 1
        for x in items
    )

    selected_fresh = sum(
        age_days(x) <= 1
        for x in selected
    )

    print('========================================')
    print('BUILD VERSION: V8')
    print('Derniere synchronisation:', sync_label)
    print('Nouveaux articles:', new_count)
    print('Posts:', len(items))
    print('Articles du jour:', today_count)
    print('Articles de la veille:', yesterday_count)
    print('Photos disponibles:', photo_count)
    print('Fiches DataScout:', report_count)
    print('Selectionnes:', len(chosen))
    print('Selection recente:', selected_fresh)
    print('========================================')

    for item in selected:
        print(
            'SELECTION:',
            item.get('date'),
            item.get('score'),
            item.get('title')
        )


if __name__ == '__main__':
    main()
