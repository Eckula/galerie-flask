:: start_windows.bat — lancer localement sous Windows
@echo off
setlocal
set FLASK_APP=app.py
set FLASK_ENV=production

:: Migrations si présentes (ne bloque pas si rien à migrer)
flask db upgrade

:: Serveur WSGI compatible Windows
waitress-serve --listen=127.0.0.1:5000 app:app

pause
