from flask import Flask, render_template_string
import threading
import time
import webbrowser

app = Flask(__name__)

# Simple HTML template with "Hello World"
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Hello World</title>
</head>
<body>
    <h1><!-- Bidvertiser2096140 --></h1>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

def open_browser():
    time.sleep(1)
    webbrowser.open_new('http://0.0.0.0:8080')

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    open_browser()
