"""Source-linked revision queue. Ratings are self-reported, not mastery scores."""
import json
from datetime import datetime, timedelta, timezone


def now():return datetime.now(timezone.utc)


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS study_reviews(
        quiz_id INTEGER PRIMARY KEY REFERENCES quizzes(id) ON DELETE CASCADE,
        due TEXT NOT NULL, interval INTEGER NOT NULL DEFAULT 0,
        reviews INTEGER NOT NULL DEFAULT 0)''')
    db.execute("""INSERT OR IGNORE INTO study_reviews(quiz_id,due)
        SELECT id,? FROM quizzes WHERE verified=1 AND invalid_reason=''
        AND selected IS NOT NULL AND selected!=correct""",(now().isoformat(),))


def record(db,qid):
    db.execute("""INSERT OR IGNORE INTO study_reviews(quiz_id,due)
        SELECT id,? FROM quizzes WHERE id=? AND verified=1 AND invalid_reason=''
        AND selected IS NOT NULL AND selected!=correct""",(now().isoformat(),qid))


def state(db):
    rows=db.execute("""SELECT r.*,q.question,q.explanation,q.sources,q.document_id,q.section_id,
        d.title AS document_title FROM study_reviews r JOIN quizzes q ON q.id=r.quiz_id
        LEFT JOIN documents d ON d.id=q.document_id WHERE q.invalid_reason=''
        ORDER BY r.due,r.quiz_id""").fetchall()
    return [dict(r)|{'sources':json.loads(r['sources'])} for r in rows]


def rate(db,qid,grade):
    if grade not in ('again','good'):raise ValueError('Choisis À revoir ou Compris.')
    row=db.execute("SELECT r.* FROM study_reviews r JOIN quizzes q ON q.id=r.quiz_id WHERE r.quiz_id=? AND q.invalid_reason=''",(qid,)).fetchone()
    if not row:raise ValueError('Cette révision est introuvable ou la question a été signalée.')
    if datetime.fromisoformat(row['due'])>now():raise ValueError('Cette révision est déjà planifiée. Reviens à son échéance.')
    interval=0 if grade=='again' else min(30,max(1,row['interval']*2))
    due=now()+(timedelta(days=interval) if interval else timedelta(minutes=10))
    db.execute('UPDATE study_reviews SET due=?,interval=?,reviews=reviews+1 WHERE quiz_id=?',(due.isoformat(),interval,qid))
    return {'ok':True}


def report(db,qid):
    if not db.execute('SELECT 1 FROM quizzes WHERE id=?',(qid,)).fetchone():raise ValueError('Question introuvable.')
    db.execute("UPDATE quizzes SET invalid_reason='Question signalée comme ambiguë : exclue des révisions et des résultats.' WHERE id=?",(qid,))
    return {'ok':True}
