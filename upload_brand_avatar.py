"""Upload the approved brand avatar to the bot configured locally in .env."""
import json
import os
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from main import Bot, load_env


def main():
    load_env()
    token = os.environ['TELEGRAM_BOT_TOKEN']
    photo = Path(__file__).resolve().parent / 'assets' / 'nf-store-avatar-4k.jpg'
    boundary = 'NFStore' + uuid.uuid4().hex
    part = json.dumps({'type': 'static', 'photo': 'attach://avatar'})
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="photo"\r\n\r\n{part}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="avatar"; filename="nf-store-avatar.jpg"\r\n'
        'Content-Type: image/jpeg\r\n\r\n'
    ).encode() + photo.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    request = Request('https://api.telegram.org/bot' + token + '/setMyProfilePhoto', data=body,
                      headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get('description', 'Profile photo upload rejected')
        except ValueError:
            detail = 'Profile photo upload rejected'
        raise SystemExit(detail) from None
    except (URLError, OSError):
        raise SystemExit('Connection failed during profile photo upload.') from None
    if result.get('ok') is not True:
        raise SystemExit('Telegram did not confirm the profile photo update.')
    bot = Bot()
    bot.token = token
    me = bot.tg('getMe')
    photos = bot.tg('getUserProfilePhotos', user_id=me['id'], limit=1)
    print(json.dumps({'profile_photo_updated': True, 'photo_visible': photos.get('total_count', 0) > 0,
                      'username': me['username']}))


if __name__ == '__main__':
    main()
