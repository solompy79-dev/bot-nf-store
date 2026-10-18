import concurrent.futures
import io
import json
import sys
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageDraw
from main import load_env
from storefront import Storefront

load_env()
bot = Storefront()
packs = json.loads(Path('bot/runtime.stickers.json').read_text(encoding='utf-8'))
name = sys.argv[1] if len(sys.argv) > 1 else 'Ai_Complex'
stickers = packs[name]['stickers']
sheet = Image.new('RGB', (800, ((len(stickers) + 7) // 8) * 120), '#444444')
draw = ImageDraw.Draw(sheet)

def get_image(item):
    index, sticker = item
    try:
        path = bot.tg('getFile', file_id=sticker['thumbnail']['file_id'])['file_path']
        with urlopen('https://api.telegram.org/file/bot' + bot.token + '/' + path, timeout=20) as r:
            picture = Image.open(io.BytesIO(r.read())).convert('RGBA')
        picture.thumbnail((80, 85))
        return index, picture
    except Exception:
        return index, None

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for index, picture in pool.map(get_image, enumerate(stickers)):
        x, y = (index % 8) * 100, (index // 8) * 120
        if picture:
            sheet.paste(picture, (x + 10, y + 5), picture)
        draw.text((x + 10, y + 95), str(index), fill='white')
sheet.save('bot/runtime.' + name + '.png')
print('Preview saved:', name)
