import json
import unittest
import app
import test_learning

class FreshInstallTests(unittest.TestCase):
    setUp=test_learning.LearningTests.setUp
    tearDown=test_learning.LearningTests.tearDown

    def test_empty_install_and_repeat_start(self):
        app.init()
        with app.connect() as db:
            for table in ('documents','courses','certifications','messages','cards','memories','jobs','media_jobs','quizzes'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0,table)
            settings=json.loads(db.execute('SELECT value FROM settings').fetchone()[0])
            self.assertNotIn('CDSA',settings['goal'])
            self.assertFalse(settings['model'].startswith('account:'))
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
