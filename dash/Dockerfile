FROM python:3.12-slim
RUN pip install --no-cache-dir requests defusedxml tzdata "pywebpush>=2,<3"
WORKDIR /app
COPY dash.py index.html fx.js sw.js manifest.webmanifest logo.png favicon.png icon-192.png icon-512.png icon-maskable.png apple-touch-icon.png ./
COPY character-libre ./character-libre
# le personnage RedRock (licence non commerciale) est facultatif : le motif copie character/ s'il existe, sinon rien (l'app prend Boulon)
COPY characte[r] ./character
COPY vendor ./vendor
USER 1000:1000
CMD ["python", "-u", "dash.py"]
