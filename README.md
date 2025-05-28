# Running `app.py`

## Prerequisites

Ensure you have Python installed. If not, download and install it from [Python's official website](https://www.python.org/downloads/).

## Installation and Setup

### Step 1: Install Python Virtual Environment

```sh
sudo apt-get install python3-venv  # For Debian-based systems
```

### Step 2: Create a Virtual Environment

```sh
python3 -m venv venv
```

### Step 3: Activate the Virtual Environment

For Linux/macOS:

```sh
source venv/bin/activate
```

For Windows (PowerShell):

```sh
venv\Scripts\Activate
```

## Running the Application

### Start `app.py` in the Background with Logging

```sh
nohup python3 app.py > app.log 2>&1 &
```

### Checking Logs

You can check the logs by running:

```sh
tail -f app.log
```

### Stopping the Application

To stop the application, find its process ID (PID) using:

```sh
ps aux | grep app.py
```

Then, kill the process:

```sh
kill <PID>
```

## Deactivating the Virtual Environment

To deactivate the virtual environment, simply run:

```sh
deactivate
```

This will return you to the system’s default Python environment.
