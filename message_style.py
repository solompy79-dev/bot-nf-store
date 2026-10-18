"""Telegram-native typography, with literal customer data and UTF-16 offsets."""

HEADINGS = ('🛍', '🎁', '👛', '📦', '💬', '🛡', '🔗', '💱', '🌐', '🟡', '🔴',
            '🧾', '🔑', '📎', '⚙', '⏳', '⌛', '⚠', '✅', '📧', '📱', '📊',
            '💳', '💰', '🚚', '📤', '👤', '🔐', '🔎', '🔌', '📝', '✏')


def units(value):
    return len(value.encode('utf-16-le')) // 2


def styled_text(text, limit=4096):
    if not isinstance(text, str) or not text.startswith(HEADINGS):
        return text, []
    # Keep the literal text and spacing. Extra ornaments wrap on small screens;
    # Telegram-native bold supplies emphasis without adding visual clutter.
    entities, offset = [], 0
    for index, line in enumerate(text.splitlines(keepends=True)):
        content = line.rstrip('\r\n')
        length = 0
        if index == 0:
            length = units(content)
        elif content.startswith(HEADINGS):
            if ':' in content:
                length = units(content.split(':', 1)[0] + ':')
            elif len(content) <= 70:
                length = units(content)
        if length:
            entities.append({'type': 'bold', 'offset': offset, 'length': length})
        offset += units(line)
    return text, entities


def style_request(method, body):
    body = dict(body)
    if method in ('sendMessage', 'editMessageText'):
        if 'parse_mode' not in body and 'entities' not in body and isinstance(body.get('text'), str):
            body['text'], entities = styled_text(body['text'])
            if entities:
                body['entities'] = entities
    elif method in ('sendPhoto', 'sendVideo', 'sendDocument', 'editMessageCaption'):
        if 'parse_mode' not in body and 'caption_entities' not in body and isinstance(body.get('caption'), str):
            body['caption'], entities = styled_text(body['caption'], limit=1024)
            if entities:
                body['caption_entities'] = entities
    elif method == 'editMessageMedia' and isinstance(body.get('media'), dict):
        media = dict(body['media'])
        if 'parse_mode' not in media and 'caption_entities' not in media and isinstance(media.get('caption'), str):
            media['caption'], entities = styled_text(media['caption'], limit=1024)
            if entities:
                media['caption_entities'] = entities
        body['media'] = media
    return body
