@echo off
rem Lance l'interface web de lm_agent (accessible uniquement depuis ce PC).
rem Double-clique sur ce fichier : le navigateur s'ouvre sur http://127.0.0.1:8765
rem Pour arreter : bouton "Quitter" dans l'interface (ou ferme cette fenetre).
cd /d "%~dp0"
python web\app.py
rem La fenetre reste ouverte seulement en cas d'erreur, pour pouvoir la lire.
if errorlevel 1 pause
