from flask import Flask, render_template_string
import threading
import time
import webbrowser

app = Flask(__name__)

# HTML template with push notification script
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="300">
    <title>Push Notification Page</title>
</head>
<body>
    <script type="application/javascript">
        pn_idzone = 5455362;
        pn_sleep_seconds = 0;
        pn_is_self_hosted = 0;
        pn_soft_ask = 1;
        pn_filename = "/worker.js";
        pn_soft_ask_horizontal_position = "left";
        pn_soft_ask_vertical_position = "top";
        pn_soft_ask_title_enabled = 1;
        pn_soft_ask_title = "Click ALLOW to continue";
        pn_soft_ask_description = "Would you like to receive great special offers & promotions?";
        pn_soft_ask_yes = "ALLOW";
        pn_soft_ask_no = "NO, THANKS"; 
    </script>
    <script type="application/javascript" src="https://js.wpnsrv.com/pn.php"></script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

def open_browser():
    # Wait a moment to ensure the server is up
    time.sleep(1)
    webbrowser.open_new('http://0.0.0.0:8080')

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

    # Open the browser
    open_browser()
