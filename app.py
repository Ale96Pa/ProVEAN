if True:
    import eventlet
    # Monkey patch the socketio server to allow using
    # blocking code inside background tasks.
    eventlet.monkey_patch()

import sys
import glob
from typing import Optional

import eventlet.wsgi
from flask import Flask, send_from_directory


from server.server import VisProgAGServer
from server.logging import Logger

# Create the Flask app
app = Flask(__name__)


@app.route('/<path:path>')
def send_report(path):
    return send_from_directory('client/dist', path)


@app.route('/')
def send_index():
    return send_from_directory('client/dist', 'index.html')


def find_networks():
    networks = glob.glob("network/*.json")
    return networks


def load_new_model(model_path: str):
    """
    Stops the current server, then tells the main thread
    to start a new one with the given model_path.
    """
    global server, next_model_path

    if not server:
        return
    next_model_path = model_path
    server.close()


# The currently open server
server: Optional[VisProgAGServer] = None
# The next path to select
next_model_path: Optional[str] = None
# The available networks.
networks = find_networks()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python app.py <model_path>")
        print("Available models:")
        for network in networks[:6]:
            print("  ", network)
        if len(networks) > 6:
            print("   ...")
        sys.exit(1)
    else:
        model_path = sys.argv[1]
    # Set the first path manually
    next_model_path = model_path

    while next_model_path is not None:
        model_name = next_model_path.split("/")[-1].split(".")[0]
        Logger.info(f"Starting a new server for model `{model_name}`")
        server = VisProgAGServer(app, next_model_path,
                                 load_new_model, networks)
        next_model_path = None
        # Start the server on port 46715
        tcp_socket = eventlet.listen(('0.0.0.0', 46715))
        eventlet.wsgi.server(tcp_socket, app, debug=False)
        Logger.info(f"Server for model `{model_name}` closed")
