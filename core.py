"""Strict prefill parsing; no guessing of respondent answers."""
import re
from urllib.parse import urlsplit, parse_qs, urlencode


def form_url(raw):
    if not isinstance(raw, str):
        raise ValueError('Enter a published Google Forms URL.')
    u = urlsplit(raw.strip())
    if u.scheme != 'https' or u.netloc != 'docs.google.com' or u.username or u.password:
        raise ValueError('Use https://docs.google.com/forms/d/e/.../viewform (expand short links first).')
    m = re.fullmatch(r'/forms/d/e/([A-Za-z0-9_-]+)/viewform', u.path)
    if not m:
        raise ValueError('Use the published /forms/d/e/.../viewform URL, not an editor or shortened link.')
    return 'https://docs.google.com' + u.path


def parse_prefill(raw, target):
    if form_url(raw) != form_url(target):
        raise ValueError('Both links must refer to the same form. Get a new prefilled link for your test copy.')
    rows = []
    for key, values in parse_qs(urlsplit(raw).query, keep_blank_values=True).items():
        if re.fullmatch(r'entry\.\d+(?:_(?:year|month|day|hour|minute))?', key):
            rows.append({'id': key, 'label': '', 'answers': values})
    if not rows:
        raise ValueError('No entry IDs found. Use Google Forms → Get pre-filled link, with every field answered.')
    return rows


def validate_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 300:
        raise ValueError('Provide between 1 and 300 answer fields.')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid answer row.')
        key, values = row.get('id', ''), row.get('answers')
        if not re.fullmatch(r'entry\.\d+(?:_(?:year|month|day|hour|minute))?', key) or key in seen:
            raise ValueError('Entry IDs must be valid and unique.')
        seen.add(key)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or len(v) > 10000 for v in values):
            raise ValueError('Each field needs a list of text answers.')
    return rows


def build_url(target, rows):
    return form_url(target) + '?' + urlencode([(r['id'], v) for r in validate_rows(rows) for v in r['answers']])
