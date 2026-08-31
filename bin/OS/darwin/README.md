macOS (Apple Silicon and Intel)
===============================

This folder is the macOS counterpart of `OS/linux` and `OS/win32`. Where those
two ship prebuilt binaries, macOS has none upstream, so everything here is
compiled locally from the sources that travel with the repository.

`Code/__init__.py` picks the folder from `sys.platform`, so on macOS
`Code.folder_os` resolves to this directory and `FasterCode` plus `OSEngines`
are imported from here.


Setting up
----------

1. **Xcode command line tools** — `xcode-select --install`.

2. **A virtualenv with the dependencies:**

   ```bash
   cd <repo>
   python3.12 -m venv .venv          # 3.12 or newer
   .venv/bin/pip install -r requirements.txt cython setuptools
   ```

3. **Build FasterCode** (the Cython extension wrapping the Irina engine core).
   The resulting `.so` is tagged with the interpreter version, so build it with
   the same interpreter you will run the GUI with:

   ```bash
   bin/_fastercode/fastercode_macos.sh "$PWD/.venv/bin/python"
   cp bin/_fastercode/src/FasterCode.cpython-*-darwin.so bin/OS/darwin/
   ```

4. **Build the engines:**

   ```bash
   bin/OS/darwin/BuildEngines.py            # everything
   bin/OS/darwin/BuildEngines.py --list     # what is installed, what is not
   ```

5. **Run it:**

   ```bash
   cd bin && ../.venv/bin/python LucasR.py
   ```


Engines
-------

`BuildEngines.py` extracts each engine's source archive from
`OS/linux/Engines/<key>/`, applies `patches/<key>.patch` if present, builds it,
checks the binary answers `uci`, and installs it as
`Engines/<folder>/<exe>` — the filenames come from parsing
`OS/linux/OSEngines.py`, so they cannot drift out of step with the registry.

Not every engine can be built. Some ship no source archive at all (andscacs,
clarabit, critter, gaviota, godel, jabba, octochess, zappa); lc0 and maia ship a
Leela tarball that needs meson, protobuf and a backend, which this script does
not attempt. Of the rest, several are x86-only at the source level, are missing
headers that were stripped from the archive, or fail to compile under libc++ and
current language standards. `OSEngines.py` in this folder
registers an engine **only when its executable is actually present**, so a
partial build is always safe — a missing engine is simply not offered in the
GUI.

Beyond the Xcode toolchain, a handful of engines need another compiler.
`BuildEngines.py` reports "needs <tool>" and moves on when one is absent:

| Tool    | Install                | Engines                            |
|---------|------------------------|------------------------------------|
| `go`    | `brew install go`      | counter, zurichess                 |
| `cargo` | `rustup`               | asymptote, hactar, velvet          |
| `fpc`   | `brew install fpc`     | alouette                           |
| `ldc2`  | `brew install ldc`     | amoeba                             |
| `cmake` | `brew install cmake`   | fallback path for several engines   |

Two engines fetch declared dependencies from the network at build time, the
normal behaviour of their toolchains: `zurichess` pulls
`bitbucket.org/zurichess/board` through the Go module proxy, and `asymptote`
pulls `arrayvec`, `crossbeam` and `rand` from crates.io.

Built binaries are ad-hoc signed (`codesign --sign -`) so Gatekeeper does not
kill them on first launch.

Two engines build cleanly but are deliberately not registered, see `UNSUPPORTED`
in `BuildEngines.py` and the comments in `OSEngines.py`: **dragontooth** (the
0.3 source answers only `go wtime/btime` and hangs on the `go depth` /
`go movetime` the GUI sends) and **sissa** (compiles and answers UCI, but its
search reports depth 30 after ~600 nodes and misses a mate in 1, identically at
-O0).


`app/` -- the .app bundle and .dmg
----------------------------------

`app/BuildApp.py` packages everything above into `Lucas Chess R6.app`, and
optionally a compressed disk image:

```bash
.venv/bin/pip install pyinstaller
bin/OS/darwin/app/BuildApp.py --dmg --python "$PWD/.venv/bin/python"
```

Both land in `app/dist/`. Roughly 535 MB for the bundle, 232 MB for the .dmg,
which carries the app and a shortcut to `/Applications`.

`app/LucasChess.spec` is the PyInstaller spec; run it through `BuildApp.py`
rather than calling `pyinstaller` yourself, because the script also does the
things the spec cannot: it deletes the log files engines leave in their own
folders (fractal's `chesslog` grows without bound, and a stale one had baked
2.4 GB into an early build), restores the execute bit on the engine binaries,
and ad-hoc signs each nested engine before sealing the bundle -- without that
inner signing, the bundle signature does not validate.

Everything collected lands under `sys._MEIPASS`, and `Code/__init__.py` treats
that folder as both `bin/` and the folder above it when `Code.frozen` is set, so
`OS/darwin` and `Resources` keep the names the source layout uses.

An app bundle is read-only and signed, so the program cannot write inside it.
`Code.folder_writable` sends `UserData`, `lc.folder` and `bug.log` to
`~/Library/Application Support/Lucas Chess R6/` when frozen, and to the folder
above `bin/` when running from source, as before.

`--sign-identity "Developer ID Application: ..."` signs with a real identity.
Without one the bundle is ad-hoc signed and therefore not notarized, so a
downloaded copy stays quarantined until that is cleared:

```bash
xattr -dr com.apple.quarantine "/Applications/Lucas Chess R6.app"
```

The icon in `app/LucasChess.icns` is generated from the app's own 64×64
`Aplicacion64` artwork, the largest that exists in the repository, so the big
icon sizes are upscaled and look soft. Replacing `app/icon_source_64.png` with
larger art and regenerating with `iconutil` would fix that.


`patches/`
----------

Unified diffs against the pristine source archive, applied with `patch -p1` from
the extracted root. They exist to make the source compile as arm64 with clang;
each hunk carries a comment saying why. The recurring themes:

* x86 inline assembly (`bsr`, `popcnt`, `cpuid`) selected by a macro that tests
  `__LP64__` — true on arm64 too — where a compiler builtin works everywhere.
* calls that became ambiguous or ill-formed under libc++ and current language
  standards.

`cargo/`
--------

Reconstructed `Cargo.toml` files for the Rust engines: the archives contain
`src/*.rs` but not the manifest, so it has to be supplied. Dependency versions
are pinned to what the code's API usage requires, and the reasoning is in a
comment at the top of each file.


What is not supported
---------------------

* **Digital boards** (`Eboard`). The drivers are distributed only as Linux `.so`
  and Windows `.dll`, so `Eboard.activate()` returns `False` on macOS and the
  configuration dialog offers only "None".
* **In-app updates.** Upstream publishes updater channels for Windows and Linux
  only; `Update.updates_supported()` is `False` here and the check is skipped.
* **Stockfish CPU-variant selection.** `CheckEngines` picks between x86-64
  microarchitecture builds; a single native build is shipped here instead, so
  that selection is skipped.
