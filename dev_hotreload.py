# dev_hotreload.py
from livereload import Server
from app import app  # app = create_app() déjà fait dans app.py

server = Server(app.wsgi_app)
# Watch templates et tout le static
server.watch('templates/**/*.html')
server.watch('templates/*.html')
server.watch('static/**/*.*')
server.watch('static/*.*')

# Lance sur 5001 avec debug
server.serve(host='127.0.0.1', port=5001, debug=True)
