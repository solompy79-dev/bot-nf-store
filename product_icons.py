"""Public Telegram custom-emoji IDs, visually checked against logo packs."""

# AI logos: https://t.me/addemoji/Ai_Complex
# Service logos: https://t.me/addemoji/AppLogosEmoji
ICONS = {
    'chatgpt': ('5255760585445901285', '🤖'),
    'claude': ('5256261335682941418', '✳️'),
    'canva': ('5256251637646787356', '🎨'),
    'deepseek': ('5256001142269185425', '🐳'),
    'gemini': ('5255920066171537833', '✨'),
    'grok': ('5255923532210144255', '✴️'),
    'notion': ('5255922265194791803', '📝'),
    'perplexity': ('5253668253472950605', '🔎'),
    'suno': ('5255782983700348754', '🎵'),
    'elevenlabs': ('5256011643464224080', '🎙'),
    'telegram': ('5206615520945666304', '✈️'),
    'discord': ('5204340648567667702', '🎮'),
    'youtube': ('5203926742569352936', '▶️'),
    'tiktok': ('5206594419771342462', '🎵'),
    'github': ('5208438275001318312', '🐙'),
    'instagram': ('5206586100419690484', '📸'),
    'facebook': ('5206443945592125179', '📘'),
    'linkedin': ('5253875352500993004', '💼'),
    'capcut': ('5253776628382728880', '🎬'),
    'steam': ('5212957246316641686', '🎮'),
    'spotify': ('5255990091318328240', '🎧'),
    'figma': ('5303063044551638689', '🎨'),
}


def icon_for(product):
    hint = str(product.get('brand') or '').lower()
    if hint in ICONS:
        return ICONS[hint]
    name = product['name'].lower().replace(' ', '')
    if any(term in name for term in ('chatgpt', 'codex', 'gptplus', 'gptpro')):
        return ICONS['chatgpt']
    for brand, icon in ICONS.items():
        if brand in name:
            return icon
    return '', '🛍'


def plain_buttons(markup):
    fallbacks = {value[0]: value[1] for value in ICONS.values()}
    rows = []
    for row in markup['inline_keyboard']:
        buttons = []
        for button in row:
            button = dict(button)
            icon = button.pop('icon_custom_emoji_id', None)
            if icon:
                button['text'] = fallbacks.get(icon, '🛍') + ' ' + button['text']
            buttons.append(button)
        rows.append(buttons)
    return {'inline_keyboard': rows}
