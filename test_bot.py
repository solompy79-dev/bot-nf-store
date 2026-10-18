import sqlite3
import unittest
from unittest.mock import Mock, patch

from main import ApiError, Bot, text_chunks


class RuntimeTests(unittest.TestCase):
    def test_long_emoji_delivery_respects_telegram_size(self):
        original = '😀' * 3000 + 'private delivery'
        chunks = list(text_chunks(original))
        self.assertEqual(''.join(chunks), original)
        self.assertTrue(all(len(chunk.encode('utf-16-le')) // 2 <= 3500 for chunk in chunks))

    def test_bad_update_does_not_block_future_updates(self):
        bot = Bot()
        bot.db = sqlite3.connect(':memory:')
        bot.db.execute('CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT)')
        bot.handle = Mock(side_effect=[IndexError('bad callback'), None])
        bot.send = Mock()
        try:
            bot.process_update({'update_id': 20})
            bot.process_update({'update_id': 21})
            self.assertEqual(bot.db.execute("SELECT value FROM settings WHERE name='offset'").fetchone()[0], '22')
            self.assertEqual(bot.handle.call_count, 2)
        finally:
            bot.db.close()

    def test_keyboard_is_only_attached_to_first_delivery_chunk(self):
        bot = Bot()
        bot.tg = Mock()
        bot.send(1, '😀' * 4000, {'inline_keyboard': []})
        self.assertEqual(bot.tg.call_count, 3)
        self.assertIn('reply_markup', bot.tg.call_args_list[0].kwargs)
        self.assertNotIn('reply_markup', bot.tg.call_args_list[1].kwargs)

    def test_retry_after_prevents_immediate_additional_api_requests(self):
        bot = Bot()
        bot.token = 'fake'
        with patch('main.request', side_effect=ApiError('limited', code=429, retry_after=30)) as request:
            with self.assertRaises(ApiError):
                bot.tg('sendMessage', chat_id=1, text='first')
            with self.assertRaises(ApiError):
                bot.tg('getUpdates', offset=0)
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
