from flask import Flask, render_template_string

app = Flask(__name__)

html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Home</title>
</head>
<body>
    <!-- Bidvertiser2096141 -->
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
