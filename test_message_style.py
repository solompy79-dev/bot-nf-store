import unittest

from message_style import style_request, styled_text, units


class MessageStyleTests(unittest.TestCase):
    def test_arabic_headings_and_literal_delivery_values(self):
        original = '📦 تفاصيل الطلب\n\n💰 الإجمالي: 5 EGP\n\n🔐 بيانات التسليم:\nEmail: a@example.com\nPassword: <&*_secret>'
        text, entities = styled_text(original)
        self.assertEqual(text, original)
        self.assertNotIn('✦', text)
        self.assertTrue(text.endswith('Email: a@example.com\nPassword: <&*_secret>'))
        encoded = text.encode('utf-16-le')
        spans = [encoded[e['offset']*2:(e['offset']+e['length'])*2].decode('utf-16-le') for e in entities]
        self.assertIn('💰 الإجمالي:', spans)
        self.assertNotIn('<&*_secret>', ' '.join(spans))

    def test_plain_payload_and_explicit_formatting_are_unchanged(self):
        raw = 'Email: x@example.com\nPassword: <a&b>'
        self.assertEqual(styled_text(raw), (raw, []))
        body = {'text': '🛍 Existing format', 'entities': []}
        self.assertEqual(style_request('sendMessage', body), body)

    def test_caption_limits_and_edits(self):
        caption = '🛍 ' + '😀' * 510
        text, _ = styled_text(caption, limit=1024)
        self.assertEqual(text, caption)
        self.assertLessEqual(units(text), 1024)
        body = {'media': {'type': 'photo', 'media': 'example', 'caption': '🛍 المنتج\n\n💰 السعر: 5 EGP'}}
        styled = style_request('editMessageMedia', body)
        self.assertIn('caption_entities', styled['media'])
        self.assertNotIn('caption_entities', body['media'])


if __name__ == '__main__':
    unittest.main()
