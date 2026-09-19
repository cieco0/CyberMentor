"""Local video ingestion: timestamped speech and sampled screen text."""
import hashlib
import json
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone

EXTENSIONS={'.mp4','.mkv','.mov','.webm','.avi','.m4v','.mp3','.wav','.m4a','.ogg','.flac'}
MAX_BYTES=1024**3
MAX_SECONDS=4*3600


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS media_jobs(
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    filename TEXT NOT NULL, path TEXT NOT NULL, digest TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', phase TEXT NOT NULL DEFAULT 'En attente',
    progress INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    interval INTEGER NOT NULL DEFAULT 10, created TEXT NOT NULL)''')
    if 'source_type' not in {r['name'] for r in db.execute('PRAGMA table_info(documents)')}:
        db.execute("ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'document'")


def save_upload(stream,size,folder,filename):
    suffix=Path(filename).suffix.lower()
    if suffix not in EXTENSIONS: raise ValueError('Format vidéo/audio non pris en charge.')
    if not 0<size<=MAX_BYTES: raise ValueError('Maximum 1 Go par vidéo ou audio.')
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+suffix)
    digest=hashlib.sha256();remaining=size
    try:
        with path.open('xb') as out:
            while remaining:
                chunk=stream.read(min(1024*1024,remaining))
                if not chunk: raise ValueError('Import interrompu : fichier incomplet.')
                out.write(chunk);digest.update(chunk);remaining-=len(chunk)
        return path,digest.hexdigest()
    except Exception:
        path.unlink(missing_ok=True)
        raise


def timestamp(seconds):
    n=max(0,int(seconds));return f'{n//3600:02}:{n%3600//60:02}:{n%60:02}'


def analyse(path,model_dir,interval,progress):
    import av
    from faster_whisper import WhisperModel
    from rapidocr_onnxruntime import RapidOCR
    with av.open(str(path)) as container:
        duration=(container.duration or 0)/av.time_base
        has_audio=bool(container.streams.audio);has_video=bool(container.streams.video)
        if not 0<duration<=MAX_SECONDS: raise ValueError('Durée illisible ou supérieure à 4 heures. Découpe la vidéo en parties.')
    entries=[];chars=0
    def add(second,kind,text):
        nonlocal chars
        text=text.strip()
        if not text:return
        chars+=len(text)
        if chars>1_900_000:raise ValueError('Transcription trop longue. Découpe la vidéo en parties.')
        entries.append((second,kind,text))
    if has_audio:
        progress('Transcription de la voix',1)
        if not (model_dir/'model.bin').exists():raise ValueError('Modèle vocal absent. Lance Installer-Video.cmd, puis Réessayer.')
        model=WhisperModel(str(model_dir),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        segments,info=model.transcribe(str(path),beam_size=3,vad_filter=True,condition_on_previous_text=False)
        for segment in segments:
            add(segment.start,'AUDIO',segment.text)
            progress('Transcription de la voix',min(50,int(50*segment.end/duration)))
        del model
    if has_video:
        progress('Lecture du texte à l’écran',50)
        ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
        previous=''
        with av.open(str(path)) as container:
            video=container.streams.video[0]
            for second in range(0,int(duration)+1,interval):
                container.seek(int(second*av.time_base),backward=True)
                frame=None
                for candidate in container.decode(video):
                    if candidate.time is not None and candidate.time>=second:
                        frame=candidate;break
                if frame is None:continue
                if frame.width>1920:frame=frame.reformat(width=1920,height=max(2,int(frame.height*1920/frame.width)))
                results,_=ocr(frame.to_ndarray(format='bgr24'))
                text='\n'.join(r[1] for r in (results or []) if r[2]>=0.5)
                if text and text!=previous:
                    add(second,'ÉCRAN / OCR',text);previous=text
                progress('Lecture du texte à l’écran',50+min(45,int(45*second/duration)))
        del ocr
    if not entries:raise ValueError('Aucune parole ni texte lisible détecté. Vérifie les pistes audio et la lisibilité des images.')
    entries.sort(key=lambda e:e[0])
    pages={}
    note=f'VIDÉO : transcription automatique et OCR, à vérifier. Un repère correspond à une minute (repère 1 = 00:00 à 00:59). Captures toutes les {interval} secondes : affichages brefs et schémas non décrits. Les commandes OCR peuvent contenir des erreurs ; vérifier la vidéo originale avant utilisation.\n'
    for second,kind,text in entries:
        page=int(second//60)+1
        pages.setdefault(page,[]).append(f'[{timestamp(second)} - {kind}] {text}')
    return [(p,note+'\n'.join(texts)) for p,texts in sorted(pages.items())]


def run_job(connect,add_document,queue,model_dir,jid):
    try:
        with connect() as db:
            job=dict(db.execute('SELECT * FROM media_jobs WHERE id=?',(jid,)).fetchone())
            db.execute("UPDATE media_jobs SET status='running',error='' WHERE id=?",(jid,))
        def update(phase,progress):
            with connect() as db:db.execute('UPDATE media_jobs SET phase=?,progress=? WHERE id=?',(phase,progress,jid))
        pages=analyse(Path(job['path']),model_dir,job['interval'],update)
        with connect() as db:
            result=add_document(db,{'title':job['title'],'course_id':job['course_id'],'source_type':'video'},pages=pages)
            model=json.loads(db.execute('SELECT value FROM settings').fetchone()[0])['model']
            for kind in ('summary','lesson'):queue(db,result['id'],kind,model)
            db.execute("UPDATE media_jobs SET status='done',phase='Transcription et OCR terminés',progress=100,document_id=? WHERE id=?",(result['id'],jid))
        # Only our temporary upload is removed; the user's original remains untouched.
        Path(job['path']).unlink(missing_ok=True)
    except Exception as exc:
        with connect() as db:db.execute("UPDATE media_jobs SET status='error',error=? WHERE id=?",(str(exc)[:1000],jid))


def start_worker(connect,add_document,queue,model_dir):
    with connect() as db:db.execute("UPDATE media_jobs SET status='queued' WHERE status='running'")
    def loop():
        while True:
            with connect() as db:row=db.execute("SELECT id FROM media_jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if row:run_job(connect,add_document,queue,model_dir,row['id'])
            else:threading.Event().wait(2)
    threading.Thread(target=loop,name='video-reader',daemon=True).start()
