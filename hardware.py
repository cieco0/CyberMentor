"""Read-only hardware inspection and conservative local-model recommendation."""
import json
import os
import platform
import shutil
import subprocess


def command(args):
    return subprocess.check_output(args,timeout=15,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).strip()


def recommend(ram,vram):
    if vram>=12 and ram>=24:return 'qwen3.5:9b','La mémoire graphique laisse une marge pour ce modèle de 6,6 Go et le contexte.'
    if vram>=6 and ram>=16:return 'qwen3.5:4b','Le modèle de 3,4 Go laisse davantage de marge pour tes cours et les autres applications.'
    return 'qwen3.5:2b','Un modèle léger est préférable avec cette mémoire ou en l’absence de GPU NVIDIA détecté. Sur processeur, les réponses peuvent être lentes.'


def scan(root):
    ram=0;cpu=platform.processor() or 'Non détecté';gpus=[];notes=[]
    try:
        info=json.loads(command(['powershell.exe','-NoProfile','-NonInteractive','-Command',"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; @{ram=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1).Name} | ConvertTo-Json -Compress"]))
        ram=round(int(info['ram'])/1024**3,1);cpu=info['cpu']
    except (OSError,ValueError,subprocess.SubprocessError):notes.append('Mémoire système non détectée : recommandation prudente.')
    try:
        for line in command(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits']).splitlines():
            name,memory=line.rsplit(',',1);gpus.append({'name':name.strip(),'vram':round(float(memory)/1024,1)})
    except (OSError,ValueError,subprocess.SubprocessError):notes.append('GPU NVIDIA non détecté ; les GPU AMD/Intel ne sont pas évalués par cet outil.')
    vram=max([g['vram'] for g in gpus],default=0)
    model,reason=recommend(ram,vram)
    model_dir=os.environ.get('OLLAMA_MODELS',os.path.expanduser('~/.ollama/models'))
    try:free=round(shutil.disk_usage(model_dir if os.path.exists(model_dir) else os.path.expanduser('~')).free/1024**3,1)
    except OSError:free=None
    return {'cpu':cpu,'ram':ram,'gpus':gpus,'free_gb':free,'model':model,'reason':reason,'notes':notes,'limit':'Estimation matérielle, sans benchmark : la qualité des réponses doit être comparée sur tes cours. Aucune donnée du PC n’est envoyée en ligne.'}
