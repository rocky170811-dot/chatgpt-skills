import unittest
from lead_hunter import Ledger, audit, domain, draft, score, plan_upserts

class QualityTests(unittest.TestCase):
    def test_domain_identity(self):
        self.assertEqual(domain('https://WWW.Example.com/contact'), 'example.com')
        self.assertEqual(domain('https://фцб.рф'), 'xn--90a1bg.xn--p1ai')
        self.assertNotEqual(domain('a.example.com'), domain('b.example.com'))

    def test_fail_closed_schema(self):
        with self.assertRaises(ValueError):
            audit([['Компания']])

    def test_shifted_rows_quarantined(self):
        header = ['№', 'Комментарии', 'Важная инф', 'Страна', 'Компания']
        result = audit([header, ['Россия', '', '', 'Firm', 'https://example.com']])
        self.assertEqual(result[0]['result'], 'SCHEMA_DRIFT')

    def test_unverified_fields_cannot_score(self):
        self.assertEqual(score({'smb_confirmed': 'unknown', 'phone_sales': 'likely'}), 0)
        self.assertEqual(score({'english': True, 'sector': True}), 25)
        self.assertEqual(score({'english': True, 'suppressed': True}), 0)

    def test_unapproved_claim_omitted(self):
        text = draft('Example', 'Example publishes a sales telephone number.')
        self.assertNotIn('37%', text)
        self.assertNotIn('dozens', text)

    def test_upsert_keeps_manual_fields(self):
        old = {'id': '1', 'website': 'https://example.com', 'status': 'Called', 'comment': 'Keep'}
        patch = {'id': '2', 'website': 'https://www.example.com/contact', 'status': 'New', 'comment': 'Erase'}
        result = plan_upserts([old], [patch])[0]
        self.assertEqual(result['action'], 'update')
        self.assertEqual(result['record']['id'], '1')
        self.assertEqual(result['record']['comment'], 'Keep')
        self.assertEqual(result['record']['status'], 'Called')

    def test_suppression_persists(self):
        old = {'id': '1', 'website': 'https://example.com', 'suppressed': True}
        self.assertEqual(plan_upserts([old], [dict(old, suppressed=False)]), [])

    def test_checkpoint_retries_only_pending(self):
        ledger = Ledger(':memory:')
        self.assertTrue(ledger.stage('today', [1]))
        with self.assertRaises(ValueError):
            ledger.confirm('today', [1], [2])
        self.assertTrue(ledger.stage('today', [1]))
        ledger.confirm('today', [1], [1])
        self.assertFalse(ledger.stage('today', [1]))
        with self.assertRaises(ValueError):
            ledger.stage('today', [2])

    def test_generic_job_link_does_not_confirm_employer(self):
        header = ['№', 'Комментарии', 'Важная инф', 'Страна', 'Компания']
        row = ['1', '', '', 'Россия', 'Example']
        result = audit([header, row], {'2': 'https://hh.ru/vacancies/sales'})
        self.assertIn('generic job search URL', result[0]['issues'])

if __name__ == '__main__':
    unittest.main()
