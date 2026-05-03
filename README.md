# GreenQuiz

GreenQuiz est une application web educative dediee au Green IT.  
Le projet permet de creer, gerer et jouer des quiz autour des bonnes pratiques numeriques responsables.  
L'architecture est volontairement simple et legere pour reduire l'empreinte technique (Flask, SQLite, front natif).  
L'objectif est de proposer une plateforme utile, maintenable et sobre en ressources.

## Site deploye

- Application en ligne : [https://greenproject-1f1e.onrender.com/](https://greenproject-1f1e.onrender.com/)

## Equipe et roles

- `Hugo W` - Coordination projet, développement full-stack, rédaction
- `Charles Y` - Développement full-stack, rédaction
- `Ornella T` - Rédaction, Organisation


## Stack technique et justification Green IT

- `Python + Flask` : framework minimal, faible surcouche, moins de complexite et de dependances.
- `SQLite` : base legere sans serveur dedie, adaptee a un projet pedagogique avec faible cout infra.
- `HTML/CSS/JS natifs` : pas de framework front lourd, moins de JavaScript execute et moins de transfert reseau.
- `Render` : deploiement simple et rapide, mutualisation de l'infrastructure.
- `Werkzeug security` : hash des mots de passe pour la securite sans service externe additionnel.

## Installation et lancement local

### 1) Cloner le projet

```bash
git clone https://github.com/HugoWiltEFREI/Greenquiz
cd GreenProject
```

### 2) Installer les dependances

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
