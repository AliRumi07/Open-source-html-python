from flask import Flask, render_template_string

app = Flask(__name__)

html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Centered Banner</title>
    <script id="aclib" type="text/javascript" src="//acscdn.com/script/aclib.js"></script>
    <style>
        .banner-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
    </style>
</head>
<body>
    <div class="banner-container">
        <div>
            <script type="text/javascript">
                aclib.runBanner({
                    zoneId: '8949742',
                });
            </script>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def hello_world():
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
