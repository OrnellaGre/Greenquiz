# GreenQuiz

GreenQuiz est une application web éducative dédiée au Green IT.  
Le projet permet de créer, gérer et jouer des quiz autour des bonnes pratiques numériques responsables.  
L'architecture est volontairement simple et légère pour réduire l'empreinte technique (Flask, SQLite, front natif).  
L'objectif est de proposer une plateforme utile, maintenable et sobre en ressources.

## Site deployé

- Application en ligne : [https://greenproject-1f1e.onrender.com/](https://greenproject-1f1e.onrender.com/)

## Equipe et roles

- `Hugo W` - Coordination projet, développement full-stack, rédaction
- `Charles Y` - Développement full-stack, rédaction
- `Ornella T` - Rédaction, Organisation


## Stack technique et justification Green IT

- `Python + Flask` : framework minimal, faible surcouche, moins de compléxite et de dépendances.
- `SQLite` : base légère sans serveur dédie, adaptée à un projet pedagogique avec faible cout infra.
- `HTML/CSS/JS natifs` : pas de framework front lourd, moins de JavaScript exécuté et moins de transfert réseau.
- `Render` : déploiement simple et rapide, mutualisation de l'infrastructure.
- `Werkzeug security` : hash des mots de passe pour la sécurité sans service externe additionnel.

## Installation et lancement local

### 1) Cloner le projet

```bash
git clone https://github.com/HugoWiltEFREI/Greenquiz
cd GreenProject
```

### 2) Installer les dépendances

```bash
python -m pip install -r requirements.txt
```

### 3) Lancer l'application

```bash
python app.py
```

### 4) Ouvrir dans le navigateur

- `http://127.0.0.1:8000`

## Structure du depot

```text
GreenProject/
|- app.py                    # Application Flask (routes, auth, logique quiz, init DB)
|- requirements.txt          # Dependances Python
|- README.md                 # Documentation du projet
|- database/
|  |- greenquiz.sqlite       # Base SQLite locale
|- static/
|  |- assets/
|     |- style.css           # Styles globaux
|     |- app.js              # JS client (interactions UI)
|- templates/
|  |- base.html              # Layout principal
|  |- index.html             # Accueil + listing quiz publics
|  |- login.html             # Connexion
|  |- register.html          # Inscription
|  |- account*.html          # Espace personnel (profil/modification/suppression)
|  |- users_*.html           # Ecran admin de gestion utilisateurs
|  |- quizzes_*.html         # Creation/edition/suppression quiz
|- docs/
|  |- rapport.pdf            # Rapport final
```


## Lien vers le rapport PDF

- Rapport : Rapport projet numérique durable - GRP5.pdf
