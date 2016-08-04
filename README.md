# DiOS Worker

The main task of the Worker is to establish a physical link between all available iOS devices (that are connected to the worker via USB) and the backend. Whenever a new device is connected to a worker for the first time via USB, it is automatically set up and registered with the backend. Afterwards, the worker constantly polls the backend for pending jobs and, on demand, initiates app installations and app launches on the connected iOS devices. The worker component was implemented in Python.

## Requirements
### Python packages

  - BeautifulSoup 4 (http://www.crummy.com/software/BeautifulSoup/)
  - requests 
  - argparse
  - plists
  - lxml (used for plists parsing error workarounds)

### Tools

  - libimobiledevice
  - libimobiledevice-utils
  - ideviceinstaller

  
## Install

Almost all tools should be available via common package managers (e.g., apt on Linux or homebrew on OS X)
BeatifulSoup 4 is probably not available via apt and needs to be installed via `pip` or manually.

```
pip install beautifulsoup4 requests argparse plists
```

`libimobiledevice` is available via homebrew:

```
brew install libimobiledevice  
brew install --HEAD ideviceinstaller  
```

and apt:

```
apt-get install libimobiledevice-utils ideviceinstaller
```

## Running the Worker

`./worker.py -b http://<hostname>.local/`


## Additional scripts

### appImporter.py

Import IPA archives from iTunes into the DiOS backend.

### scheduler.py

Schedule execution jobs from various sources (iTunes RSS feeds, bundleId, ...)

### setAppleIDPassword.py

Add the Apple ID password to the backend to enable automated App Store purchases. 
CAUTION: Use Apple IDs with payment credentials at you own risk!!! By default, DiOS may automatically make purchases!!! The password will be stored UNENCRYPTED!!!


