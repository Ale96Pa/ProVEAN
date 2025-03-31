FROM python:3.12.4-bookworm

RUN apt-get update && apt-get install -y npm
# Install the stuff to compile pygraphviz
RUN apt-get install -y graphviz graphviz-dev
# Before copying other things...
WORKDIR /app
COPY requirements.txt /app/requirements.txt
# Create a venv for the python packages with the version 
RUN python3 -m venv /app/venv
# Activate the venv
ENV PATH="/app/venv/bin:$PATH"
# Install the python packages
RUN pip install -r requirements.txt
RUN pip install pygraphviz tqdm

# Copy the data relevant to the client
COPY client /app/client
# Install the npm packages
WORKDIR /app/client
RUN npm install && npm run build

# Copy the data relevant to the server
WORKDIR /app
COPY server /app/server
COPY progag /app/progag
# Copy the files to the container
COPY app.py /app/app.py
COPY generate_network.py /app/generate_network.py
# Copy the network examples
COPY examples/small.json /app/network/small.json
COPY examples/medium.json /app/network/medium.json
COPY examples/large.json /app/network/large.json

# Expose the port
EXPOSE 46715
CMD ["python3", "app.py", "network/small.json"]
