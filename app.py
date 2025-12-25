import os
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    # Get params from Environment (passed via Docker -e)
    app_version = os.getenv('APP_VERSION', '1.0.0')
    bg_color = os.getenv('BG_COLOR', 'white')
    
    html = f"""
    <html>
        <head><title>FinTech Secure App</title></head>
        <body style="background-color: {bg_color}; font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>FinTech Secure Payment Gateway</h1>
            <hr>
            <h3>Version: {app_version}</h3>
            <p>Status: <span style="color:green; font-weight:bold;">SECURE</span></p>
        </body>
    </html>
    """
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7979)