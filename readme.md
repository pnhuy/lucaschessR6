Lucas Chess (R6)
================

Lucas Chess (R6) is a GUI of chess:

1. To train in many different ways.
2. To play chess against any UCI engine.
3. To compete against engines to obtain an elo.
4. It has utilities to edit games, create polyglot books, tournaments between engines ...

This is an update of Lucas Chess with a new version of python (3.7 -> 3.12) and the main graphic library, from pyside2 to pyside6 (qt5 -> qt6).


Incompatibilities
-----------------
* **Does not support Windows 8 or previous versions.**
* **Not compatible with 32-bit operating systems.**


macOS
-----

Windows and Linux ship prebuilt binaries; macOS does not, so on macOS the
FasterCode extension and the chess engines are compiled from the sources in this
repository. See [bin/OS/darwin/README.md](bin/OS/darwin/README.md) for the full
setup, in short:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt cython setuptools
bin/_fastercode/fastercode_macos.sh "$PWD/.venv/bin/python"
cp bin/_fastercode/src/FasterCode.cpython-*-darwin.so bin/OS/darwin/
bin/OS/darwin/BuildEngines.py
cd bin && ../.venv/bin/python LucasR.py
```

To package it as a double-clickable app and a disk image:

```bash
.venv/bin/pip install pyinstaller
bin/OS/darwin/app/BuildApp.py --dmg --python "$PWD/.venv/bin/python"
```

That writes `Lucas Chess R6.app` and `LucasChessR6.dmg` into
`bin/OS/darwin/app/dist/`. The bundle is only ad-hoc signed, so a copy that has
been downloaded rather than built locally needs its quarantine flag cleared
before macOS will open it:

```bash
xattr -dr com.apple.quarantine "/Applications/Lucas Chess R6.app"
```

With an Apple Developer ID the build can sign and notarize instead, so it opens
anywhere with no warning -- see "Signing and notarizing" in
[bin/OS/darwin/README.md](bin/OS/darwin/README.md):

```bash
bin/OS/darwin/app/BuildApp.py --dmg --python "$PWD/.venv/bin/python" \
    --sign-identity "Developer ID Application: Your Name (TEAMID)" \
    --notarize lucaschess
```

Only the engines that build are registered, so the engine list is smaller than
on Windows and Linux. Digital boards and in-app updates are not available. When
running from the bundle, `UserData` lives in
`~/Library/Application Support/Lucas Chess R6/` rather than beside the program.

Dependencies
------------

* Python 3.12+
* charset-normalizer
* sortedcontainers
* python-chess
* pillow
* psutil
* polib
* deep-translator
* requests
* urllib3
* idna
* certifi
* beautifulsoup4

Important Note for Developers / Cloning
---------------------------------------

This repository uses **Git LFS (Large File Storage)** to manage large binary files (such as chess engines, networks, or databases).

If you download the repository using the GitHub web interface as a **.zip file, these large files will not be included correctly** (you will only get small text pointer files).

To get a complete and working copy of the project, please ensure you have **Git LFS** installed on your system before cloning.

1. **Install Git LFS** (if you haven't already):
   - Windows: `winget install GitHub.GitLFS` or download from [git-lfs.github.com](https://git-lfs.github.com/)
   - Mac: `brew install git-lfs`
   - Linux: `sudo apt install git-lfs`

2. **Initialize Git LFS** in your terminal:
   ```bash
   git lfs install

3. Clone the repository:
   ```bash
   git clone https://github.com/lukasmonk/lucaschessR6.git

Links
-----

* Web: [https://lucaschess.pythonanywhere.com/](https://lucaschess.pythonanywhere.com/).
* Blog: [https://lucaschess.blogspot.com.es/](https://lucaschess.blogspot.com.es/).


Legal Details
-------------

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
USA

See the file "LICENSE" for details.



