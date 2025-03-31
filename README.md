# Visualization Suite for Progressive Attack Graphs

The objective of this project is to provide an interactive tool for visualizing and analyzing progressive attack graphs.

## Installation
First of all clone the repository:
```bash
git clone git@github.com:XAIber-lab/visProgAg.git && cd visProgAg
```

Then make sure you have Node.js installed on your system. The code is currently only tested with Node.js `v20.17.0`, but anything lower _should_ work as well, as long as it supports ECMAScript modules.

To install the dependencies for the frontend, change into the `client` directory and run `npm install`:
```bash
cd client
npm install
```

To install the dependencies for the backend, from **the root of the project**, run:
```bash
pip install -r requirements.txt
```

> Note that the versions of the packages were hand-picked for compatibility reasons and are only tested with Python `3.12.4`. For that reason, I personally recommend using a virtual environment of your choosing to install this specific Python version and packages.

## Usage
To start the frontend server, run:
```bash
cd client
npm run dev

# or
npm run dev -- --open # to open the browser automatically
```

Now, you will need to generate an attack graph model to analyze. You can skip this step if you already have one. To generate a model, move to another terminal and run:
```bash
python generate_network.py
```

You can pass it properties, run with `--help` to see the available options.

Finally, start the backend server with `python app.py network/model.json`. If you have generated the network model with the default name, you can run:
```bash
python app.py network/model_100h_2s_2v.json
```

### Using Docker
You can run this project with Docker.

First, build it with:
```bash
docker  built -t visprogag .
```

Then you can run it with:
```bash
docker run -p 46715:46715 visprogag 
```

Navigating to [localhost:46715](http://localhost:46715) should now show the frontend.


## Stack
There are two servers:
1. The **backend server** listening on port `46715`, running on Python 3.12 and Flask, serving the WebSocket API and performing the attack path generation and analysis.
2. The **frontend server** listening on port `5173`, running on Node.js, serving the Svelte 4 single-page application with the UI.

    > This server is only needed for development and will not be required when this software is in production. For that reason, it also proxies the WebSocket API to the backend server on path `/socket.io/`.

Languages and technologies used:
- Python 3.12
- Flask
- Svelte 4
- Node.js
- WebSockets
- TypeScript
- HTML
- CSS
