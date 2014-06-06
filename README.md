# DiOS Worker

The DiOS worker takes care of all locally connected iOS devices. This includes an automatic backend registration and polling for new jobs waiting to get executed.

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

Almost all tools are available via your package manager (i.e. apt on Linux or homebrew on OS X)
BeatifulSoup 4 is probably not available via apt and needs to be installed via `pip` or manually.

```
pip install beautifulsoup4 requests argparse plist
```

libimobiledevice is available via homebrew ...

```
brew install libimobiledevice  
brew install --HEAD ideviceinstaller  
```

and apt

```
apt-get install libimobiledevice-utils ideviceinstaller
```

## Running the worker

./worker.py -b http://`hostname.local`/


## Additional scripts

### appImporter.py

Can be used to import IPA archives from iTunes into the DiOS backend.

### scheduler.py

Schedule backend jobs from different sources (iTunes RSS feeds, bundleId, ...)

### setAppleIDPassword.py

Add the password for an AppleID to the backend to allow automated purchases. 
CAUTION: Use AppleIDs with payment credentials at you own risk!!! EVERY purchase will be done if possible!!! The password will be stored UNENCRYPTED!!!


