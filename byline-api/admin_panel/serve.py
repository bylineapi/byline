"""
Servidor local para el panel de administración de Byline
Ejecuta: python serve.py
Luego abre: http://localhost:8000
"""
import http.server
import socketserver

PORT = 8000

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Servidor iniciado en http://localhost:{PORT}")
    print(f"Abre tu navegador en: http://localhost:{PORT}")
    print("Presiona Ctrl+C para detener el servidor")
    httpd.serve_forever()
