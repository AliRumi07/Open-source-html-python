from flask import Flask, render_template_string

app = Flask(__name__)

html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Centered Content</title>
    <script id="aclib" type="text/javascript" src="//acscdn.com/script/aclib.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .content {
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="content">
        <script type="text/javascript">
            aclib.runAutoTag({
                zoneId: 'xzqj5qrw84',
            });
        </script>
    </div>
</body>
</html>
'''

@app.route('/')
def hello_world():
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
