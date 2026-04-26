# GreenQuiz - TI616 Mini Projet

GreenQuiz est une plateforme educative sobre pour sensibiliser au Green IT via des quiz.
Le projet est maintenant en **Python Flask + SQLite**, avec une architecture legere,
facile a maintenir, et limitee aux fonctions vraiment utiles.

## Fonctionnalites
- Inscription utilisateur
- Connexion / deconnexion
- Page compte (profil connecte)
- Mini quiz Green IT en front (JS local)

## Stack et justification Green IT
- `Flask` : framework minimal, peu de code boilerplate.
- `SQLite` : base locale legere, sans serveur externe.
- `HTML/CSS/JS natifs` : peu de dependances, peu de requetes HTTP.
- `System fonts` : pas d'appel a des polices externes.

## Structure du depot
- `app.py` : application Flask + routes + initialisation DB
- `templates/` : pages HTML (base, accueil, auth, compte)
- `static/assets/` : CSS + JS minimaux
- `database/greenquiz.sqlite` : base locale
- `docs/` : rapport et preuves de mesure

## Lancer le projet
1. Installer les dependances:
   - `python3 -m pip install -r requirements.txt`
2. Lancer le serveur:
   - `python3 app.py`
3. Ouvrir:
   - `http://127.0.0.1:8000`

## Remarques
- La base SQLite est creee automatiquement au premier lancement.
- Le mot de passe est stocke avec hash (`werkzeug.security`).
