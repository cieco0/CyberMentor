# CyberMentor

Assistant personnel pour apprendre la cybersécurité, organiser ses cours et préparer ses certifications. Interface en français, base SQLite locale, modèles Ollama ou comptes personnels via les outils officiels.

## Installation sur un autre PC Windows

1. Télécharge le ZIP du dépôt (bouton **Code → Download ZIP**) et extrais-le, ou clone le dépôt avec Git.
2. Installe **Python 3.11 ou 3.12 (64 bits)** depuis https://www.python.org/downloads/windows/ en cochant l’ajout au PATH.
3. Double-clique sur **Lancer.cmd**. Au premier lancement, un environnement `.venv` est créé et les dépendances sont téléchargées. Internet est nécessaire ; cette étape peut prendre plusieurs minutes.
4. Ouvre http://127.0.0.1:8765. L’application démarre vierge : aucun cours, aucune certification, aucune conversation personnelle.
5. Pour une IA locale, lance **Installer-IA.cmd**. Ce script installe Ollama et télécharge `qwen2.5:7b`. Dans les réglages, tu peux analyser ton PC, télécharger un autre modèle, choisir un modèle installé ou en supprimer un inutilisé.
6. Personnalise ton profil dans **Réglages**, ajoute tes certifications puis tes espaces **Cours / Certifications**.

**Arreter.cmd** arrête le serveur. Fermer le navigateur ne l’arrête pas. N’expose pas ce serveur personnel sur Internet : il écoute uniquement sur `127.0.0.1`.

## Étudier au quotidien

- **Accueil** : reprendre la dernière discussion de cours, voir les révisions dues ou choisir un exercice.
- **Mes cours** : organiser les supports et leurs résumés.
- **M’entraîner** : QCM, explication avec tes mots, exemple ou lab guidé étape par étape.
- **Mes révisions** : les erreurs sur les QCM validés conservent leur correction et leurs extraits sources. Choisis « À revoir » pour un rappel dans dix minutes, ou « Compris » pour espacer les rappels (1, 2, 4 jours, jusqu’à 30 jours). Ce choix est une autoévaluation, pas une preuve de maîtrise.
- Une question ambiguë peut être signalée depuis la correction ou les révisions ; elle est alors exclue du suivi.
- Les réglages, la bibliothèque et les objectifs sont regroupés sous **Organiser mon espace**.

## Ce qui est inclus

- Import multiple de PDF avec texte sélectionnable, DOCX, TXT et Markdown.
- Espaces par cours, sections, résumés expliqués exportables en PDF.
- Questions fondées sur les passages retrouvés, QCM avec correction expliquée, labs guidés, cartes de révision et mémoire personnelle.
- Fichiers vidéo/audio : transcription locale et OCR périodique de l’écran. Lance **Installer-Video.cmd** pour préparer le modèle vocal. Les PDF scannés nécessitent un OCR externe.
- Analyse du matériel et gestion des modèles Ollama.
- Connexion facultative aux comptes ChatGPT via Codex et Claude via Claude Code. Les réponses restent dans l’interface CyberMentor.

## Comptes ChatGPT et Claude (facultatifs)

Installe l’outil officiel correspondant sur le nouveau PC, puis utilise **Réglages → Comptes liés** :

- Codex : https://developers.openai.com/codex/cli/
- Claude Code : https://code.claude.com/docs/en/setup

Connecte-toi avec ton propre compte sur la page officielle. Les identifiants et sessions de l’autre PC ne sont jamais copiés dans ce dépôt. Selon le compte, un abonnement compatible est nécessaire. L’utilisation dépend des limites et règles du fournisseur. Ces connecteurs utilisent les interfaces des outils officiels, qui peuvent évoluer ; une mise à jour de CyberMentor peut devenir nécessaire.

Avec Ollama, le traitement est local. Avec un compte lié, tes questions et le contexte utilisé (dont les extraits de cours) sont envoyés au fournisseur choisi. Aucun compte distant n’est activé au premier lancement.

## Version vierge et données personnelles

Le dépôt contient uniquement le programme, ses tests et ses scripts. Il ne contient ni cours, ni base de données, ni sauvegarde, ni journal, ni modèle téléchargé, ni clé, ni connexion personnelle.

Au premier lancement, `data/mentor.sqlite3` est créée avec un profil générique et une discussion vide. Les dossiers de données sont exclus de Git. Tes nouvelles données sur ce PC sont indépendantes de celles de l’autre PC.

Pour sauvegarder ton utilisation future, utilise le bouton de sauvegarde dans Réglages. Ne publie pas cette sauvegarde dans le dépôt. Pour repartir de zéro, utilise une nouvelle copie du programme dans un autre dossier après avoir arrêté la précédente, sans copier son dossier `data`.

## Limites

Le modèle n’est pas réentraîné : CyberMentor recherche des extraits et prépare des synthèses. La recherche est lexicale. Les réponses et les QCM peuvent contenir des erreurs : vérifie les informations importantes dans les sources. L’analyse vidéo utilise transcription et captures OCR, pas une compréhension continue des images. Les labs proposent des commandes à exécuter toi-même.

Les recommandations matérielles sont des estimations, pas des benchmarks. Les modèles locaux doivent être téléchargés séparément sur chaque PC.

## Développement

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

Node.js est facultatif et permet de vérifier le JavaScript avec `node --check web/app.js`.
