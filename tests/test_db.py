import os
import tempfile
import unittest

import importlib


class TestDBSeed(unittest.TestCase):
    def test_seed_profiles_created(self):
        # use temporary DB path to avoid overwriting real db
        import config
        old_path = config.DB_PATH
        fd, tmp = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        config.DB_PATH = tmp
        # reload db module
        import db as dbmod
        importlib.reload(dbmod)
        dbmod.init_db()
        profiles = dbmod.get_all_profiles()
        usernames = {p['username'] for p in profiles}
        expected = {'SkeeYee_j','Cannella_S','nurkotik','FAFNIR5','thebitsamuraiizz','doob_rider','Tecno2027','kixxzzl','L9g9nda'}
        self.assertTrue(expected.issubset(usernames))
        # cleanup
        os.remove(tmp)
        config.DB_PATH = old_path

    def test_reports_insert_and_fetch(self):
        import config
        old_path = config.DB_PATH
        fd, tmp = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        config.DB_PATH = tmp
        import db as dbmod
        importlib.reload(dbmod)
        dbmod.init_db()

        r = {
            'reporter_id': 111,
            'reporter_username': 'reporter1',
            'category': 'bot',
            'target_identifier': 'target1',
            'reason': 'Test reason',
            'attachments': None,
            'created_at': '2025-01-01T00:00:00'
        }
        rid = dbmod.add_report(r)
        reports = dbmod.get_reports()
        self.assertTrue(any(rep['id'] == rid for rep in reports))

        # cleanup
        os.remove(tmp)
        config.DB_PATH = old_path

    def test_add_profile_status_and_review(self):
        import config
        old_path = config.DB_PATH
        fd, tmp = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        config.DB_PATH = tmp
        import db as dbmod
        importlib.reload(dbmod)
        dbmod.init_db()

        # create a user-submitted profile -> status should default to 'pending'
        p = {
            'username': 'test_user_1',
            'age': 20,
            'name': 'Тест',
            'added_by': 'tester',
            'added_by_id': 12345,
        }
        pid = dbmod.add_profile(p)
        rec = dbmod.get_profile_by_id(pid)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.get('status'), 'pending')

        # accept the profile programmatically
        ok = dbmod.update_profile_status_by_id(pid, 'approved')
        self.assertTrue(ok)
        rec2 = dbmod.get_profile_by_id(pid)
        self.assertEqual(rec2.get('status'), 'approved')

        # cleanup
        os.remove(tmp)
        config.DB_PATH = old_path


if __name__ == '__main__':
    unittest.main()
