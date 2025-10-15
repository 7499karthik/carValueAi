from flask import Flask, send_from_directory, send_file
import os

app = Flask(__name__, static_folder='static', static_url_path='')

@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/auth.html')
def auth():
    return send_file('static/auth.html')

@app.route('/<path:path>')
def serve_static(path):
    if path.endswith('.html'):
        return send_file(f'static/{path}')
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
