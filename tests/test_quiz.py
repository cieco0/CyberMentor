import json
import unittest
from unittest.mock import patch
import app
import quiz
import test_learning


class QuizTests(unittest.TestCase):
    setUp=test_learning.LearningTests.setUp
    tearDown=test_learning.LearningTests.tearDown

    def start(self):
        sample={'question':'Que fait pwd ?\nCorrection: A est la bonne réponse.','options':['Affiche le dossier courant','Efface un fichier','Change le mot de passe','Éteint le PC'],'correct':0,'explanation':'pwd affiche le chemin du répertoire où se trouve actuellement le terminal.','source_index':1}
        with app.connect() as db:
            doc=app.add_document(db,{'title':'Linux','text':'La commande pwd affiche le chemin du répertoire courant du terminal.'})['id']
        with app.connect() as db,patch.object(app,'generate',side_effect=[json.dumps(sample),json.dumps({'valid':True,'correct':0,'explanation':sample['explanation']})]):
            app.ask(db,{'session_id':1,'document_id':doc,'mode':'quiz','question':'Crée un QCM.'})
        return doc,sample

    def test_solution_hidden_then_wrong_answer_explained_and_locked(self):
        doc,sample=self.start()
        with app.connect() as db:
            visible=app.state(db)['quiz'];qid=visible['id']
            self.assertNotIn('correct',visible);self.assertNotIn('explanation',visible)
            self.assertEqual(visible['question'],'Que fait pwd ?')
            self.assertNotIn('Correction:',app.state(db)['messages'][-1]['content'])
            self.assertEqual(len(visible['options']),4)
            self.assertNotIn(sample['explanation'],app.state(db)['messages'][-1]['content'])
        with app.connect() as db,patch.object(app,'generate',side_effect=AssertionError('Correction locale')):
            reply=app.ask(db,{'session_id':1,'document_id':doc,'mode':'quiz','question':'B','quiz_id':qid})
            self.assertIn('Pas tout à fait',reply['answer']);self.assertIn('Pourquoi',reply['answer']);self.assertIn(sample['explanation'],reply['answer'])
            self.assertEqual(app.state(db)['quiz']['selected'],1)
            self.assertEqual(app.state(db)['quiz']['correct'],0)
        with app.connect() as db:
            with self.assertRaises(ValueError):app.ask(db,{'document_id':doc,'mode':'quiz','question':'A','quiz_id':qid})

    def test_correct_answer_also_explained_and_wrong_scope_rejected(self):
        doc,sample=self.start()
        with app.connect() as db:
            with self.assertRaises(ValueError):app.ask(db,{'document_id':None,'mode':'quiz','question':'A'})
            reply=app.ask(db,{'document_id':doc,'mode':'quiz','question':'A'})
            self.assertIn('Bonne réponse !',reply['answer']);self.assertIn(sample['explanation'],reply['answer'])
            qid=quiz.current(db,1)['id']
        sample['options']=['Identique']*4
        with self.assertRaises(ValueError),app.connect() as db,patch.object(app,'generate',return_value=json.dumps(sample)):
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'Question suivante','quiz_id':qid})
        with app.connect() as db:self.assertEqual(quiz.current(db,1)['id'],qid)

    def test_letter_choices_rejected_and_prefixes_normalized(self):
        with self.assertRaises(ValueError):quiz.normalize_options(['A','B','C','D'])
        self.assertEqual(quiz.normalize_options(['A) Linux','B. Windows','(C) macOS','D) BSD']),['Linux','Windows','macOS','BSD'])
        with self.assertRaises(ValueError):quiz.normalize_options(['A) Linux','B) Linux','C) BSD','D) Windows'])

    def test_disagreement_retries_without_saving_bad_question(self):
        doc,sample=self.start()
        with app.connect() as db:
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'A'})
            previous=quiz.current(db,1)['id']
        wrong={'valid':True,'correct':2,'explanation':'Une autre réponse.'}
        with self.assertRaises(ValueError),app.connect() as db,patch.object(app,'generate',side_effect=[json.dumps(sample),json.dumps(wrong)]*2) as generate:
            app.ask(db,{'document_id':doc,'mode':'quiz','question':'Question suivante'})
        self.assertEqual(generate.call_count,4)
        with app.connect() as db:self.assertEqual(quiz.current(db,1)['id'],previous)

    def test_invalid_legacy_question_annulled_without_grading(self):
        doc,_=self.start()
        with app.connect() as db:
            db.execute('UPDATE quizzes SET options=?,verified=0',(json.dumps(['A','B','C','D']),))
            quiz.migrate(db);quiz.migrate(db)
            visible=quiz.public(db,1)
            self.assertTrue(visible['invalid_reason'])
            self.assertNotIn('correct',visible)
            reply=app.ask(db,{'document_id':doc,'mode':'quiz','question':'D'})
            self.assertIn('annulée',reply['answer'])
            self.assertNotIn('Pas tout',reply['answer'])
            self.assertIsNone(quiz.current(db,1)['selected'])

    def test_ambiguous_boot_order_rejected(self):
        _,sample=self.start()
        sample['question']='Quel est le premier processus après le BIOS/UEFI ?'
        with self.assertRaisesRegex(ValueError,'Chronologie'):
            quiz.create_candidate({'model':'local'},'','',{},[{'text':'cours'}],lambda *a,**k:json.dumps(sample))
