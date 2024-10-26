from flask import Flask, render_template_string
import threading
import time
import webbrowser

app = Flask(__name__)

# HTML template with video player and VAST integration
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="300">
    <title>Video Player with VAST</title>
    <script src="https://cdn.jsdelivr.net/npm/video.js@7/dist/video.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/videojs-contrib-ads@6/dist/videojs.ads.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/videojs-ima@2/dist/videojs.ima.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/video.js@7/dist/video-js.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/videojs-contrib-ads@6/dist/videojs.ads.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/videojs-ima@2/dist/videojs.ima.css" rel="stylesheet">
</head>
<body>
    <video-js id="content_video" class="video-js vjs-default-skin" controls preload="auto" width="640" height="360">
        <!-- You can add a source video here if needed -->
        <source src="https://storage.googleapis.com/gvabox/media/samples/stock.mp4" type="video/mp4">
    </video-js>

    <script>
        var player = videojs('content_video');

        var options = {
            id: 'content_video',
            adTagUrl: 'https://s.magsrv.com/v1/vast.php?idzone=5455340'
        };

        player.ima(options);
        player.ima.requestAds();
        player.play();
    </script>
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
