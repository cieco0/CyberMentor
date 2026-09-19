"""Background Ollama downloads; course data is never sent to the registry."""
import json
import re
import threading
import urllib.request


class ModelUpdate:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {'status': 'idle', 'model': '', 'detail': '', 'completed': 0, 'total': 0}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self, model):
        if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*(?:/[a-zA-Z0-9][a-zA-Z0-9_.-]*)?(?::[a-zA-Z0-9][a-zA-Z0-9_.-]*)?', model) or len(model)>100 or 'cloud' in model.lower():
            raise ValueError('Indique un nom de modèle local valide, par exemple qwen2.5:7b.')
        with self.lock:
            if self.state['status'] == 'running':
                raise ValueError('Un téléchargement est déjà en cours.')
            self.state = {'status': 'running', 'model': model, 'detail': 'Connexion à Ollama…', 'completed': 0, 'total': 0}
        threading.Thread(target=self.run, args=(model,), daemon=True).start()
        return self.snapshot()

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def run(self, model):
        try:
            request = urllib.request.Request('http://127.0.0.1:11434/api/pull', data=json.dumps({'model': model, 'stream': True}).encode(), headers={'Content-Type': 'application/json'})
            success = False
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get('error'):
                        raise ValueError(item['error'])
                    detail = item.get('status', 'Téléchargement…')
                    self.update(detail=detail, completed=item.get('completed', 0), total=item.get('total', 0))
                    if detail == 'success':
                        success = True
            if not success:
                raise ValueError('Téléchargement interrompu. Relance pour reprendre les fichiers déjà reçus.')
            self.update(status='done', detail='Modèle téléchargé ou déjà à jour. Enregistre tes préférences pour utiliser ce modèle.')
        except Exception as error:
            self.update(status='error', detail='Mise à jour impossible : '+str(error)+'. Vérifie qu’Ollama est lancé et que la connexion Internet fonctionne, puis réessaie.')
