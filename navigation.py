"""One replaceable navigation message per chat; receipts are never tracked here."""
from main import ApiError


class Navigation:
    def init_navigation(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS navigation_message(chat INTEGER PRIMARY KEY, message INTEGER NOT NULL, kind TEXT NOT NULL)')
        self.db.commit()

    def current_menu(self, chat):
        row = self.db.execute('SELECT message,kind FROM navigation_message WHERE chat=?', (chat,)).fetchone()
        return (row[0], row[1]) if row else None

    def forget_menu(self, chat):
        old = self.current_menu(chat)
        if old:
            try:
                self.tg('deleteMessage', chat_id=chat, message_id=old[0])
            except ApiError:
                pass  # A failed cleanup must never block the next screen.
            self.db.execute('DELETE FROM navigation_message WHERE chat=?', (chat,))
            self.db.commit()

    def remember_menu(self, chat, result, kind='text'):
        identity = result.get('message_id') if isinstance(result, dict) else None
        if type(identity) is not int:
            return
        old = self.current_menu(chat)
        if old and old[0] != identity:
            self.forget_menu(chat)
        self.db.execute('INSERT OR REPLACE INTO navigation_message VALUES (?,?,?)', (chat, identity, kind))
        self.db.commit()

    def menu_message(self, chat, text, markup=None):
        old = self.current_menu(chat)
        # Reply keyboards require a new sendMessage. Photos also require a new
        # text message; remember_menu deletes the old screen only after success.
        if old and old[1] == 'text' and not (markup and 'keyboard' in markup):
            try:
                return self.tg('editMessageText', chat_id=chat, message_id=old[0],
                               text=text, reply_markup=markup or {'inline_keyboard': []})
            except ApiError as exc:
                if exc.not_modified:
                    return
                if exc.code != 400:
                    raise
        result = self.send(chat, text, markup)
        self.remember_menu(chat, result)
        return result

    def record_message(self, chat, text, markup=None):
        """Preserve the new receipt/key/payment details, retire only the old menu."""
        result = self.send(chat, text, markup)
        self.forget_menu(chat)
        return result
