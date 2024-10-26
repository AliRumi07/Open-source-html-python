from flask import Flask

app = Flask(__name__)

@app.route('/')
def show_app_ads():
    try:
        with open('app-ads.txt', 'r') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return 'app-ads.txt file not found'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
