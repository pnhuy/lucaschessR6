#!/usr/bin/env python3
"""Build "Lucas Chess R6.app", and optionally a .dmg to hand out.

This wraps PyInstaller with the steps a bare `pyinstaller LucasChess.spec` does
not do: clearing the log files engines leave in their own folders, restoring the
execute bit on the engine binaries that PyInstaller collects as data, ad-hoc
signing every nested engine and then the bundle as a whole, and building a
compressed disk image.

    ./BuildApp.py                 # build the .app
    ./BuildApp.py --dmg           # build the .app and then the .dmg
    ./BuildApp.py --dmg --clean   # discard previous build state first

    # signed and notarized, for handing to other people
    ./BuildApp.py --dmg \
        --sign-identity "Developer ID Application: Your Name (TEAMID)" \
        --notarize lucaschess

Prerequisites: the engines must already be built (`../BuildEngines.py`) and
FasterCode must be present in `../` -- see ../README.md. PyInstaller has to be
installed in the interpreter used to run this script's `--python`, which
defaults to the interpreter running this file.

A note on Gatekeeper: without an Apple Developer ID the bundle can only be
ad-hoc signed, and macOS will refuse to open it from a downloaded .dmg until the
quarantine flag is cleared. See "Signing and notarizing" in ../README.md for the
one-time setup that --notarize expects.
"""

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
import sys
from typing import Any, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
DARWIN = os.path.dirname(HERE)
ENGINES = os.path.join(DARWIN, "Engines")
SPEC = os.path.join(HERE, "LucasChess.spec")
ENTITLEMENTS = os.path.join(HERE, "entitlements.plist")
DIST = os.path.join(HERE, "dist")
WORK = os.path.join(HERE, "build")
APP_NAME = "Lucas Chess R6.app"
APP = os.path.join(DIST, APP_NAME)

# Same list the spec filters on; applied to the source tree too, so a stale log
# from a test run does not sit around at 2 GB.
JUNK_NAMES = {"chesslog", "bug.log"}
JUNK_SUFFIXES = (".log", ".tmp", ".profraw", ".profdata")


def run(cmd: Sequence[str], **kw: Any) -> "subprocess.CompletedProcess[bytes]":
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.run(list(cmd), check=True, **kw)


def clean_engine_junk() -> None:
    """Delete run-time droppings from the engine folders."""
    removed = 0
    freed = 0
    for dirpath, _dirs, files in os.walk(ENGINES):
        for name in files:
            if name in JUNK_NAMES or name.endswith(JUNK_SUFFIXES):
                path = os.path.join(dirpath, name)
                try:
                    freed += os.path.getsize(path)
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
    if removed:
        print(f"  removed {removed} engine log/temp file(s), {freed / 1e6:.1f} MB")


def engine_binaries(root: str) -> List[str]:
    """Mach-O files under the collected Engines tree, real files only."""
    out = []
    engines_root = os.path.join(root, "Contents", "Frameworks", "OS", "darwin", "Engines")
    for dirpath, _dirs, files in os.walk(engines_root):
        for name in files:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as f:
                    magic = f.read(4)
            except OSError:
                continue
            if magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                out.append(path)
    return out


def all_macho(root: str) -> List[str]:
    """Every real Mach-O file in the bundle, deepest paths first.

    Notarization rejects any unsigned or ad-hoc signed binary anywhere in the
    bundle, not only the engines: the Python libraries and extension modules
    PyInstaller collects under Contents/Frameworks count too. Deepest first so a
    nested binary is signed before whatever contains it.
    """
    magics = (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as f:
                    if f.read(4) in magics:
                        out.append(path)
            except OSError:
                continue
    out.sort(key=lambda p: (p.count(os.sep), p), reverse=True)
    return out


def fix_permissions(binaries: Sequence[str]) -> None:
    for path in binaries:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  execute bit set on {len(binaries)} engine binaries")


def sign(paths: Sequence[str], identity: Optional[str],
         entitlements: Optional[str] = None) -> int:
    """Sign each path, reporting failures rather than dying on the first one.

    With a real identity the Hardened Runtime and a secure timestamp are added,
    both of which notarization requires. Ad-hoc signing ("-") supports neither,
    and is only good enough to run the bundle locally.
    """
    if identity:
        args = ["--force", "--options", "runtime", "--timestamp", "--sign", identity]
        if entitlements:
            args += ["--entitlements", entitlements]
    else:
        args = ["--force", "--timestamp=none", "--sign", "-"]

    failed = []
    for path in paths:
        p = subprocess.run(["codesign", *args, path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            failed.append((path, (p.stderr or "").strip().splitlines()[-1:]))
    if failed:
        print(f"  WARNING: {len(failed)} signature(s) failed, first: {failed[0]}")
    return len(paths) - len(failed)


def notarize(path: str, profile: str) -> None:
    """Submit to Apple, wait for the verdict, then staple the ticket.

    Stapling is what lets the result work offline; without it Gatekeeper has to
    ask Apple on first launch.
    """
    target = path
    cleanup = None
    if path.endswith(".app"):
        # notarytool takes an archive, not a bundle directory.
        target = path + ".zip"
        run(["ditto", "-c", "-k", "--keepParent", path, target])
        cleanup = target

    print(f"  submitting {os.path.basename(target)} to Apple, this takes a few minutes")
    # `--wait` exits 0 even when Apple rejects the submission, so read the verdict.
    print("  $ xcrun notarytool submit ... --wait", flush=True)
    result = subprocess.run(["xcrun", "notarytool", "submit", target,
                             "--keychain-profile", profile, "--wait"],
                            capture_output=True, text=True)
    print(result.stdout[-2000:], flush=True)
    if cleanup:
        os.remove(cleanup)
    if result.returncode != 0 or "status: Accepted" not in result.stdout:
        sub_id = next((ln.split(":", 1)[1].strip() for ln in result.stdout.splitlines()
                       if ln.strip().startswith("id:")), "<id>")
        sys.exit(f"Notarization of {os.path.basename(path)} was not accepted. Reasons: "
                 f"xcrun notarytool log {sub_id} --keychain-profile {profile}")

    # A .dmg and a .app can both be stapled; the zip cannot.
    run(["xcrun", "stapler", "staple", path])
    print(f"  stapled {os.path.basename(path)}")


def build_app(python: str, clean: bool, identity: Optional[str],
              notarize_profile: Optional[str] = None) -> str:
    print("Cleaning engine logs")
    clean_engine_junk()

    print("Running PyInstaller")
    cmd = [python, "-m", "PyInstaller", "--noconfirm",
           "--distpath", DIST, "--workpath", WORK, SPEC]
    if clean:
        cmd.insert(3, "--clean")
    run(cmd)

    if not os.path.isdir(APP):
        sys.exit(f"PyInstaller did not produce {APP}")

    print("Fixing engine permissions")
    binaries = engine_binaries(APP)
    fix_permissions(binaries)

    # The engines are nested Mach-O executables. They have to carry their own
    # signature before the enclosing bundle is sealed, or the bundle signature
    # will not validate.
    nested = all_macho(APP)
    print(f"Signing {len(nested)} nested binaries ({len(binaries)} of them engines)")
    sign(nested, identity)

    print("Signing the bundle")
    sign([APP], identity, ENTITLEMENTS if identity else None)
    run(["codesign", "--verify", "--deep", "--strict", APP])

    if notarize_profile:
        print("Notarizing the bundle")
        notarize(APP, notarize_profile)

    size = subprocess.run(["du", "-sh", APP], capture_output=True, text=True).stdout.split()[0]
    plist = os.path.join(APP, "Contents", "Info.plist")
    with open(plist, "rb") as f:
        version = plistlib.load(f).get("CFBundleShortVersionString", "?")
    print(f"\n{APP_NAME} {version} built, {size}")
    return APP


def build_dmg(identity: Optional[str] = None, notarize_profile: Optional[str] = None,
              volname: str = "Lucas Chess R6") -> str:
    """Compressed disk image with the app and a shortcut to /Applications."""
    dmg = os.path.join(DIST, "LucasChessR6.dmg")
    staging = os.path.join(WORK, "dmg")
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)

    print("\nStaging the disk image")
    # -R, not copytree: symlinks inside the bundle must stay symlinks, and the
    # execute bits must survive.
    run(["cp", "-R", APP, os.path.join(staging, APP_NAME)])
    os.symlink("/Applications", os.path.join(staging, "Applications"))

    if os.path.exists(dmg):
        os.remove(dmg)
    print("Creating the disk image (this compresses ~2 GB, give it a few minutes)")
    run(["hdiutil", "create", "-volname", volname, "-srcfolder", staging,
         "-ov", "-format", "UDZO", "-imagekey", "zlib-level=6", dmg])
    shutil.rmtree(staging, ignore_errors=True)

    if identity:
        print("Signing the disk image")
        sign([dmg], identity)
    if notarize_profile:
        print("Notarizing the disk image")
        notarize(dmg, notarize_profile)

    size = subprocess.run(["du", "-sh", dmg], capture_output=True, text=True).stdout.split()[0]
    print(f"\n{os.path.basename(dmg)} built, {size}")
    return dmg


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dmg", action="store_true", help="also build the .dmg")
    parser.add_argument("--clean", action="store_true",
                        help="pass --clean to PyInstaller, discarding cached state")
    parser.add_argument("--python", default=sys.executable,
                        help="interpreter that has PyInstaller and the app's dependencies")
    parser.add_argument("--sign-identity", default=None,
                        help='codesign identity, e.g. "Developer ID Application: '
                             'Name (TEAMID)"; default is ad-hoc ("-")')
    parser.add_argument("--notarize", metavar="KEYCHAIN_PROFILE", default=None,
                        help="notarize and staple using credentials previously stored "
                             "with `xcrun notarytool store-credentials`; requires "
                             "--sign-identity")
    args = parser.parse_args()

    if sys.platform != "darwin":
        sys.exit("BuildApp.py builds a macOS bundle; run it on macOS.")
    if not os.path.isdir(ENGINES) or not os.listdir(ENGINES):
        sys.exit(f"No engines in {ENGINES} -- run ../BuildEngines.py first.")

    if args.notarize and not args.sign_identity:
        sys.exit("--notarize needs --sign-identity: Apple will not notarize an "
                 "ad-hoc signature.")

    build_app(args.python, args.clean, args.sign_identity, args.notarize)
    if args.dmg:
        build_dmg(args.sign_identity, args.notarize)

    if args.notarize:
        print("\nNotarized and stapled. It will open on any Mac with no warning.")
    elif not args.sign_identity:
        print("\nAd-hoc signed, so not notarized. Opening it from a downloaded\n"
              ".dmg needs the quarantine flag cleared:\n"
              '  xattr -dr com.apple.quarantine "/Applications/Lucas Chess R6.app"')


if __name__ == "__main__":
    main()
