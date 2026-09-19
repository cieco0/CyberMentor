"""Personal account bridge using official local CLIs, without API keys."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

MODELS={'account:chatgpt':'codex','account:claude':'claude'}
_logins={}
_lock=threading.Lock()


def executable(kind):
    if kind not in ('codex','claude'):raise ValueError('Compte inconnu.')
    found=shutil.which(kind+'.exe') or shutil.which(kind)
    if found:return found
    if kind=='claude':
        candidate=Path.home()/'.local/bin/claude.exe'
        return str(candidate) if candidate.exists() else None
    candidates=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))
    return str(max(candidates,key=lambda p:p.stat().st_mtime)) if candidates else None


def environment():
    env=os.environ.copy()
    for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','OPENAI_BASE_URL','CLAUDE_CODE_OAUTH_TOKEN'):
        env.pop(key,None)
    return env


def run(args,**kwargs):
    return subprocess.run(args,encoding='utf-8',errors='replace',capture_output=True,env=environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),**kwargs)


def status(kind):
    exe=executable(kind)
    if not exe:return {'installed':False,'connected':False,'detail':'Outil officiel non installé.'}
    try:
        result=run([exe,'login','status'] if kind=='codex' else [exe,'auth','status'],timeout=20)
        if kind=='codex':connected=result.returncode==0 and 'using ChatGPT' in result.stdout+result.stderr
        else:
            data=json.loads(result.stdout)
            connected=result.returncode==0 and data.get('loggedIn') is True and data.get('authMethod') in ('claude.ai','oauth')
        return {'installed':True,'connected':connected,'detail':'Compte connecté.' if connected else 'Connecte ton compte avec le bouton ci-dessous.'}
    except (OSError,ValueError,subprocess.SubprocessError):
        return {'installed':True,'connected':False,'detail':'Connexion non confirmée. Relance la connexion officielle.'}


def login(kind):
    exe=executable(kind)
    if not exe:raise ValueError('Installe l’outil officiel avant de connecter ce compte.')
    with _lock:
        active=_logins.get(kind)
        if active and active.poll() is None:return {'started':True}
        args=[exe,'login'] if kind=='codex' else [exe,'auth','login']
        process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        _logins[kind]=process
        def expire():
            try:process.wait(timeout=300)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        threading.Thread(target=expire,daemon=True).start()
    return {'started':True}


def generate(model,system,messages,limit=1800,format=None):
    kind=MODELS[model]
    if not status(kind)['connected']:raise ValueError('Reconnecte ton compte dans Réglages → Comptes liés.')
    # No shell interpolation; course text goes to stdin, never into arguments.
    prompt=system+'\nRéponds uniquement au contenu fourni, sans outil. Réponse concise (environ '+str(limit)+' tokens maximum).'
    if format:prompt+='\nRetourne uniquement du JSON respectant ce schéma : '+json.dumps(format,ensure_ascii=False)
    prompt+='\nÉCHANGES :\n'+json.dumps(messages,ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix='cybermentor-chat-') as folder:
        exe=executable(kind)
        if kind=='codex':
            args=[exe,'exec','--ignore-user-config','--ignore-rules','--sandbox','read-only','--skip-git-repo-check','--ephemeral','--json','-c','web_search="disabled"','-c','approval_policy="never"','-c','project_doc_max_bytes=0','--enable','skip_host_skill_discovery']
            for feature in ('shell_tool','apps','plugins','multi_agent','browser_use','computer_use','code_mode_host','view_image','hooks','memories','shell_snapshot','workspace_dependencies'):
                args+=['--disable',feature]
            args+=['-']
        else:
            args=[exe,'-p','--safe-mode','--tools','','--disallowedTools','*','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--output-format','json']
        try:result=run(args,input=prompt,cwd=folder,timeout=300)
        except subprocess.TimeoutExpired:raise ValueError('Le compte distant met trop de temps à répondre. Réessaie.') from None
        if result.returncode:raise ValueError('Réponse du compte indisponible : vérifie la connexion, ton abonnement et ses limites. Aucun basculement automatique vers une API payante.')
        if kind=='codex':
            events=[json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith('{')]
            if any(e.get('type')=='turn.failed' for e in events):raise ValueError('Le compte ChatGPT n’a pas terminé la réponse. Vérifie ses limites.')
            answers=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
            answer=answers[-1] if answers else ''
        else:
            data=json.loads(result.stdout)
            if data.get('is_error'):raise ValueError('Claude n’a pas terminé la réponse. Vérifie ton abonnement et ses limites.')
            answer=data.get('result','')
        if not answer.strip():raise ValueError('Le compte a renvoyé une réponse vide.')
        if format:
            # Some CLIs wrap JSON despite the instruction; remove only a complete fence.
            answer=answer.strip()
            if answer.startswith('```') and answer.endswith('```'):answer=answer.split('\n',1)[1].rsplit('```',1)[0].strip()
            json.loads(answer)
        return answer
