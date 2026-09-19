import unittest
from unittest.mock import patch
from datetime import timedelta
import app
import quiz
import study
import test_quiz


class StudyTests(unittest.TestCase):
    setUp=test_quiz.QuizTests.setUp
    tearDown=test_quiz.QuizTests.tearDown
    start=test_quiz.QuizTests.start

    def test_error_is_saved_once_with_source_and_spaced_ratings(self):
        doc,_=self.start()
        with app.connect() as db:
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'B'})
            qid=quiz.current(db,1)['id']
            study.migrate(db);study.record(db,qid)
            rows=study.state(db)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['sources'][0]['document_id'],doc)
            self.assertEqual(rows[0]['document_title'],'Linux')
            study.rate(db,qid,'good')
            self.assertEqual(study.state(db)[0]['interval'],1)
            with self.assertRaises(ValueError):study.rate(db,qid,'good')
            future=study.now()+timedelta(days=2)
            with patch.object(study,'now',return_value=future):study.rate(db,qid,'again')
            self.assertEqual(study.state(db)[0]['interval'],0)

    def test_correct_answers_not_marked_as_difficulties(self):
        doc,_=self.start()
        with app.connect() as db:
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'A'})
            self.assertEqual(study.state(db),[])

    def test_report_excludes_item_and_prevents_grading(self):
        doc,_=self.start()
        with app.connect() as db:
            qid=quiz.current(db,1)['id']
            study.report(db,qid)
            reply=app.ask(db,{'document_id':doc,'mode':'quiz','question':'B'})
            self.assertIn('annulée',reply['answer'])
            self.assertIsNone(quiz.current(db,1)['selected'])
            self.assertEqual(study.state(db),[])

    def test_report_removes_existing_review_and_delete_cascades(self):
        doc,_=self.start()
        with app.connect() as db:
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'B'})
            qid=quiz.current(db,1)['id']
            study.report(db,qid)
            self.assertEqual(study.state(db),[])
            with self.assertRaises(ValueError):study.rate(db,qid,'good')
            db.execute('DELETE FROM documents WHERE id=?',(doc,))
            self.assertEqual(db.execute('SELECT count(*) FROM study_reviews').fetchone()[0],0)
