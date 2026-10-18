import sqlite3
import unittest
from unittest.mock import Mock

from main import ApiError
from navigation import Navigation


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.nav = Navigation()
        self.nav.db = sqlite3.connect(':memory:')
        self.nav.tg = Mock(return_value={'message_id': 20})
        self.nav.send = Mock(return_value={'message_id': 20})
        self.nav.init_navigation()

    def tearDown(self):
        self.nav.db.close()

    def test_text_navigation_edits_one_message(self):
        self.nav.remember_menu(1, {'message_id': 10})
        self.nav.menu_message(1, 'Product details', {'inline_keyboard': []})
        self.nav.tg.assert_called_once_with('editMessageText', chat_id=1, message_id=10,
                                           text='Product details', reply_markup={'inline_keyboard': []})
        self.nav.send.assert_not_called()
        self.assertEqual(self.nav.current_menu(1), (10, 'text'))

    def test_photo_to_text_deletes_only_after_success(self):
        self.nav.remember_menu(1, {'message_id': 10}, 'photo')
        self.nav.send.side_effect = ApiError('send failed')
        with self.assertRaises(ApiError):
            self.nav.menu_message(1, 'Product list')
        self.nav.tg.assert_not_called()
        self.assertEqual(self.nav.current_menu(1), (10, 'photo'))
        self.nav.send.side_effect = None
        self.nav.menu_message(1, 'Product list')
        self.nav.tg.assert_called_once_with('deleteMessage', chat_id=1, message_id=10)
        self.assertEqual(self.nav.current_menu(1), (20, 'text'))

    def test_receipts_are_not_navigation_messages(self):
        self.nav.remember_menu(1, {'message_id': 10})
        self.nav.record_message(1, 'Private delivery data')
        self.assertIsNone(self.nav.current_menu(1))
        self.nav.tg.assert_called_once_with('deleteMessage', chat_id=1, message_id=10)
        self.nav.tg.reset_mock()
        self.nav.send.return_value = {'message_id': 30}
        self.nav.menu_message(1, 'Wallet')
        self.nav.tg.assert_not_called()
        self.assertEqual(self.nav.current_menu(1), (30, 'text'))

    def test_old_or_unchanged_messages_do_not_break_navigation(self):
        self.nav.remember_menu(1, {'message_id': 10})
        self.nav.tg.side_effect = ApiError('not modified', code=400, not_modified=True)
        self.nav.menu_message(1, 'Same screen')
        self.nav.send.assert_not_called()
        self.nav.tg.side_effect = ApiError('too old', code=400)
        self.nav.menu_message(1, 'New screen')
        self.assertEqual(self.nav.current_menu(1), (20, 'text'))

    def test_new_home_keyboard_and_chats_are_independent(self):
        self.nav.remember_menu(1, {'message_id': 10})
        self.nav.remember_menu(2, {'message_id': 40})
        self.nav.menu_message(1, 'Home', {'keyboard': [[{'text': 'Products'}]]})
        self.assertEqual(self.nav.current_menu(1), (20, 'text'))
        self.assertEqual(self.nav.current_menu(2), (40, 'text'))
        self.nav.tg.assert_called_once_with('deleteMessage', chat_id=1, message_id=10)


if __name__ == '__main__':
    unittest.main()
