#!/usr/bin/env python3
"""Build the bundled chess engines for macOS and install them into Engines/.

Lucas Chess ships the engines for Windows and Linux as prebuilt binaries. There
are no macOS builds, so on this platform they have to be compiled from the
sources that travel with the repository (OS/linux/Engines/<key>/src.7z and
friends). This script does that end to end:

    1. extract the engine's source archive into a work folder
    2. apply patches/<key>.patch if one exists (arm64 / clang portability)
    3. drop in cargo/<key>.toml for Rust engines whose Cargo.toml was stripped
       from the archive
    4. build it -- either with the recipe in RECIPES, or by walking a generic
       ladder of build strategies
    5. check the resulting binary answers UCI
    6. install it into Engines/<folder>/<exe>, using the names the engine
       registry expects, alongside the support files (books, networks,
       licences) taken from the Linux folder

Usage:

    ./BuildEngines.py                 # build everything
    ./BuildEngines.py stockfish irina # build just these
    ./BuildEngines.py --list          # show what is installed and what is not

Toolchains: Xcode command line tools are enough for most engines. A few need
more, and are skipped with a clear message when it is missing:

    go    (brew install go)   counter, zurichess
    cargo (rustup)            asymptote, hactar, velvet
    fpc   (brew install fpc)  alouette
    ldc2  (brew install ldc)  amoeba
    cmake (brew install cmake) several engines' fallback path

Engines with no macOS build stay absent from Engines/, and OSEngines.py leaves
anything absent out of the registry, so a partial run is always safe.
"""

import argparse
import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OS_DIR = os.path.dirname(HERE)
LINUX_ENGINES = os.path.join(OS_DIR, "linux", "Engines")
DARWIN_ENGINES = os.path.join(HERE, "Engines")
PATCHES = os.path.join(HERE, "patches")
CARGO = os.path.join(HERE, "cargo")
WORK = os.path.join(HERE, "_build")
SHIMS = os.path.join(WORK, "_shims")

ARCH = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()

# Flags in the shipped makefiles that clang on macOS rejects outright.
BAD_FLAGS = (
    "-m64", "-m32", "-static", "-static-libgcc", "-static-libstdc++",
    "-march=native", "-mpopcnt", "-msse", "-msse2", "-msse3", "-mssse3",
    "-msse4", "-msse4.1", "-msse4.2", "-mavx", "-mavx2", "-mbmi", "-mbmi2",
    "-mfpmath=sse", "-flto=full", "-fwhole-program", "-fprofile-generate",
    "-fprofile-use", "-fprofile-correction", "-fprofile-arcs",
    "-ftest-coverage", "-Wl,--gc-sections", "-Wl,-s", "-Wl,--no-as-needed",
)
BAD_RE = re.compile(r"(?<=[\s=])(" + "|".join(re.escape(f) for f in
                    sorted(BAD_FLAGS, key=len, reverse=True)) + r")(?=[\s\\]|$)")

CFLAGS = "-O2 -DNDEBUG -w -fno-strict-aliasing"
CXXFLAGS = CFLAGS + " -std=c++17"

MAIN_RE = re.compile(r"^[ \t]*(?:int|void)[ \t\n]+main[ \t]*\(", re.M)

# Preferred entry points when a directory holds more than one main().
MAIN_PREFERENCE = ("main", "uci", "engine")

# Engines whose build needs something the generic ladder cannot guess.
# key -> [(label, dir relative to the source root, shell command)]
RECIPES = {
    "stockfish": [(
        "make:apple-silicon", "src",
        # The nets are not in src.7z; they ship next to the Linux binary.
        f'cp "{LINUX_ENGINES}/stockfish/"*.nnue . && '
        f'make -j4 all COMP=clang '
        f'ARCH={"apple-silicon" if ARCH == "arm64" else "x86-64-modern"}',
    )],
    # SYZYGY_TBS= disables Syzygy probing, whose Fathom submodule is not in
    # src.7z. Lucas Chess ships Gaviota tablebases, not Syzygy.
    "arasan": [(
        "make:no-syzygy", "src",
        # ARASAN_VERSION is pinned: the Makefile otherwise runs `git describe`,
        # which inside this repository reports Lucas Chess's own tag.
        "rm -rf ../build ../profile ../bin ../prof_data && "
        "make -j4 CC=clang++ VERSION=22.2 ARASAN_VERSION=22.2 SYZYGY_TBS= default",
    )],
    # __int64 is an MSVC keyword that pawny's sources use unconditionally; the
    # Linux build defines it away the same way. patches/pawny.patch adds the
    # non-x86 bit operations, which the header only had as x86 assembly.
    "pawny": [("clang:msvc-int64", "src",
               f'clang {CFLAGS} -D"__int64=long long" -idirafter "{SHIMS}" '
               "-o engine_bin *.c -lm -lpthread")],
    # Free Pascal. The shipped Makefile hardcodes the author's own fpc path.
    # MACOSX_DEPLOYMENT_TARGET has to go: with it set, fpc 3.2.2 on arm64 emits a
    # misaligned thread-variable table and the link fails with
    # "ld: pointer not aligned in FPC_THREADVARTABLES".
    "alouette": [("fpc", "source",
                  "rm -rf units ../alouette && mkdir -p units && "
                  "env -u MACOSX_DEPLOYMENT_TARGET make PC=fpc alouette")],
    # D via LDC. POPCOUNT=true would add -mattr=+sse4.2,+popcnt.
    "amoeba": [("ldc2", "src",
                "make DC=ldc2 CPU=native POPCOUNT=false BUILD=fast amoeba")],
    # Rust: a reconstructed Cargo.toml is installed by prepare(); cargo does the rest.
    "asymptote": [("cargo", ".", "cargo build --release")],
    "hactar": [("cargo", ".", "cargo build --release")],
    "velvet": [("cargo", ".", "cargo build --release")],
    # Go. The module paths matter: the packages import themselves by full path.
    "counter": [("go", ".",
                 "rm -f go.mod go.sum */go.mod && "
                 "go mod init github.com/ChizhovVadim/CounterGo >/dev/null 2>&1; "
                 "go build -o engine_bin ./counter")],
    "dragontooth": [("go", ".",
                     "go mod init dragontooth >/dev/null 2>&1; "
                     "go mod tidy >/dev/null 2>&1; go build -o engine_bin .")],
    "zurichess": [("go", "src",
                   "GOFLAGS=-mod=mod go build -o engine_bin ./zurichess")],
}

# Engines that build but must not be shipped, with the reason.
UNSUPPORTED = {
    "dragontooth": "source builds 0.3, which answers only `go wtime/btime` and "
                   "hangs on the `go depth` / `go movetime` the GUI sends",
    "sissa": "builds and answers UCI, but its search is broken: depth 30 after "
             "~600 nodes and no mate in 1, identically at -O0",
}

# Tools a recipe needs, so a missing one is reported instead of failing obscurely.
NEEDS_TOOL = {"alouette": "fpc", "amoeba": "ldc2",
              "asymptote": "cargo", "hactar": "cargo", "velvet": "cargo",
              "counter": "go", "dragontooth": "go", "zurichess": "go"}

SHIM_HEADERS = {
    "malloc.h": "/* macOS has no <malloc.h>; the entry points live in <stdlib.h>. */\n"
                "#pragma once\n#include <stdlib.h>\n",
    "alloca.h": "#pragma once\n#include <stdlib.h>\n",
    "sys/sysinfo.h": """/* Minimal <sys/sysinfo.h> for macOS: only the fields engines read. */
#pragma once
#include <sys/sysctl.h>
#include <unistd.h>
#include <string.h>

struct sysinfo {
    long uptime;
    unsigned long loads[3];
    unsigned long totalram, freeram, sharedram, bufferram;
    unsigned long totalswap, freeswap;
    unsigned short procs;
    unsigned long totalhigh, freehigh;
    unsigned int mem_unit;
};

static inline int sysinfo(struct sysinfo *info) {
    if (!info) return -1;
    memset(info, 0, sizeof(*info));
    int64_t memsize = 0;
    size_t len = sizeof(memsize);
    if (sysctlbyname("hw.memsize", &memsize, &len, NULL, 0) != 0) return -1;
    info->totalram = (unsigned long)memsize;
    info->freeram = (unsigned long)memsize / 2;
    info->mem_unit = 1;
    info->procs = (unsigned short)sysconf(_SC_NPROCESSORS_ONLN);
    return 0;
}
""",
    "bits/stdc++.h": "/* libstdc++'s convenience header, absent from libc++. */\n"
                     "#pragma once\n" + "".join(
                         f"#include <{h}>\n" for h in (
                             "algorithm", "array", "bitset", "cassert", "cctype",
                             "chrono", "cmath", "cstdint", "cstdio", "cstdlib",
                             "cstring", "deque", "fstream", "functional", "iomanip",
                             "iostream", "iterator", "limits", "list", "map",
                             "memory", "numeric", "queue", "set", "sstream",
                             "stack", "string", "thread", "tuple",
                             "unordered_map", "unordered_set", "utility", "vector")),
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def write_shims():
    """Headers a few engines include that macOS does not have.

    Reached with -idirafter, never -I: on the normal include path these would
    shadow libc++'s own <stdlib.h> and break every C++ build.
    """
    for rel, body in SHIM_HEADERS.items():
        path = os.path.join(SHIMS, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(body)


def registry_names():
    """(folder, exe) per engine key, read from the Linux registry.

    Parsed rather than duplicated so the installed filenames cannot drift from
    what OSEngines.py looks for.
    """
    src = open(os.path.join(OS_DIR, "linux", "OSEngines.py")).read()
    out = {}
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "mas"):
            continue
        args = node.args
        if len(args) < 5:
            continue
        try:
            key, exe = ast.literal_eval(args[0]), ast.literal_eval(args[4])
        except ValueError:
            continue
        folder = next((ast.literal_eval(kw.value) for kw in node.keywords
                       if kw.arg == "folder"), None) or key
        out.setdefault(folder, (folder, exe))
    return out


def run(cmd, cwd, log, timeout=1800):
    env = dict(os.environ)
    env.setdefault("MACOSX_DEPLOYMENT_TARGET", "12.0")
    env["PATH"] = (os.path.expanduser("~/.cargo/bin") + ":/opt/homebrew/bin:"
                   + env.get("PATH", ""))
    log.write(f"\n$ (cd {cwd} && {cmd})\n")
    log.flush()
    try:
        proc = subprocess.run(cmd, cwd=cwd, shell=True, env=env, timeout=timeout,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log.write(proc.stdout[-20000:])
        log.flush()
        return proc.returncode
    except subprocess.TimeoutExpired:
        log.write("*** timed out\n")
        return 124


def source_archive(key):
    folder = os.path.join(LINUX_ENGINES, key)
    if not os.path.isdir(folder):
        return None
    for name in sorted(os.listdir(folder)):
        if name.lower() in ("src.7z", "source.7z", "src.zip",
                            "src.tar.gz", "source.tar.gz"):
            return os.path.join(folder, name)
    return None


def prepare(key, log):
    """Extract the source, apply the patch, install a reconstructed Cargo.toml."""
    archive = source_archive(key)
    if archive is None:
        return None
    root = os.path.join(WORK, key)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    if archive.endswith(".7z"):
        cmd = f'7z x -o"{root}" "{archive}"'
    elif archive.endswith(".zip"):
        cmd = f'unzip -q -d "{root}" "{archive}"'
    else:
        cmd = f'tar xzf "{archive}" -C "{root}"'
    if run(cmd, WORK, log, timeout=600) != 0:
        return None

    cargo_toml = os.path.join(CARGO, f"{key}.toml")
    if os.path.isfile(cargo_toml):
        shutil.copy2(cargo_toml, os.path.join(root, "Cargo.toml"))
        log.write("installed reconstructed Cargo.toml\n")

    patch = os.path.join(PATCHES, f"{key}.patch")
    if os.path.isfile(patch):
        if run(f'patch -p1 --batch < "{patch}"', root, log, timeout=120) != 0:
            log.write("*** patch did not apply cleanly\n")

    # Strip flags clang cannot take from every makefile. Whole-token
    # replacement: a substring swap would turn "-msse4.2" into ".2".
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            if name.lower() not in ("makefile", "gnumakefile") and not name.endswith(".mk"):
                continue
            path = os.path.join(dirpath, name)
            before = open(path, errors="replace").read()
            after = BAD_RE.sub(" ", before)
            if after != before:
                open(path, "w").write(after)
                log.write(f"sanitized flags in {os.path.relpath(path, root)}\n")
    return root


def dirs_containing(root, *names):
    hits = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        if any(n in files for n in names):
            hits.append(dirpath)
    hits.sort(key=lambda d: d.count(os.sep))
    return hits


def makefile_targets(path):
    try:
        text = open(path, errors="replace").read()
    except OSError:
        return []
    skip = {"clean", "cleanall", "help", "cloc", "install", "test", "strip",
            "dirs", "tuning", "utils"}
    out = []
    for target in re.findall(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?!=)", text, re.M):
        if target not in skip and target not in out:
            out.append(target)
    return out[:8]


def source_sets(dirpath, srcs):
    """Candidate source lists for compiling a directory as one program.

    Several engines keep a test or benchmark driver next to the engine, each
    with its own main(). Dropping them by filename is what breaks the link when
    the real main() calls into them, so instead find every file that defines
    main() and, when there is more than one, yield one candidate per choice --
    keeping that file and dropping the other mains.
    """
    with_main = []
    for name in srcs:
        try:
            text = open(os.path.join(dirpath, name), errors="replace").read()
        except OSError:
            continue
        if MAIN_RE.search(text):
            with_main.append(name)

    if len(with_main) <= 1:
        return [srcs]

    def rank(name):
        stem = os.path.splitext(name)[0].lower()
        return (MAIN_PREFERENCE.index(stem) if stem in MAIN_PREFERENCE else len(MAIN_PREFERENCE),
                name)

    sets = []
    for keep in sorted(with_main, key=rank)[:3]:
        sets.append([n for n in srcs if n == keep or n not in with_main])
    return sets


def include_dirs(root):
    found = set()
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "_cmake")]
        if any(f.endswith((".h", ".hpp", ".hh", ".hxx")) for f in files):
            found.add(dirpath)
    return sorted(found)


def strategies(key, root):
    """Build attempts in order, cheapest and likeliest first."""
    for label, rel, cmd in RECIPES.get(key, []):
        yield f"recipe:{label}", os.path.normpath(os.path.join(root, rel)), cmd

    for name in ("make_osx.sh", "make_ct800_mac.sh", "build_mac.sh", "build_osx.sh"):
        for d in dirs_containing(root, name):
            yield f"script:{name}", d, f"chmod +x {name} && ./{name}"

    for d in dirs_containing(root, "Makefile", "makefile", "GNUmakefile"):
        makefile = next(os.path.join(d, n) for n in ("Makefile", "makefile", "GNUmakefile")
                        if os.path.isfile(os.path.join(d, n)))
        base = (f'make -j4 CC=clang CXX=clang++ CFLAGS="{CFLAGS} -idirafter {SHIMS}" '
                f'CXXFLAGS="{CXXFLAGS} -idirafter {SHIMS}" LDFLAGS="" LFLAGS="" ')
        yield "make", d, base
        yield "make:plain", d, "make -j4 CC=clang CXX=clang++"
        for target in makefile_targets(makefile):
            yield f"make:{target}", d, base + target

    for d in dirs_containing(root, "CMakeLists.txt"):
        yield ("cmake", d,
               "rm -rf _cmake && cmake -S . -B _cmake -DCMAKE_BUILD_TYPE=Release "
               f'-DCMAKE_C_FLAGS="{CFLAGS}" -DCMAKE_CXX_FLAGS="{CXXFLAGS}" '
               f"-DCMAKE_OSX_ARCHITECTURES={ARCH} && cmake --build _cmake -j4")

    # Last resort: compile every source in a directory as one program.
    # Two include styles are tried, -iquote first. An engine's own folder may
    # hold a header sharing a name with a system one (sissa ships src/limits.h);
    # on the -I path that shadows <limits.h> for the whole translation unit.
    # But engines that reach their own headers as <subdir/header.h> need -I, so
    # that variant follows.
    quoted = " ".join(f'-iquote "{d}"' for d in include_dirs(root))
    angled = quoted + " " + " ".join(f'-I"{d}"' for d in include_dirs(root))
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "_cmake", "build", "obj")]
        for exts, lang in (((".c",), "c"), ((".cpp", ".cc", ".cxx"), "cpp")):
            all_srcs = sorted(f for f in files if f.endswith(exts))
            if not all_srcs:
                continue
            for srcs in source_sets(dirpath, all_srcs):
                cc, flags, force = (
                    ("clang", CFLAGS,
                     "-include stdint.h -include stdbool.h -include stddef.h "
                     "-include limits.h")
                    if lang == "c"
                    else ("clang++", CXXFLAGS,
                          "-include cstdint -include cstdlib -include climits"))
                names = " ".join(f'"{n}"' for n in srcs)
                rel = os.path.relpath(dirpath, root)
                variants = [("", "", quoted), (":angled", "", angled)]
                if lang == "cpp":
                    # register is a hard error from C++17 on; ordered pointer/zero
                    # comparisons likewise. Older standards still accept both.
                    variants += [(":c++20", "-std=c++20", quoted),
                                 (":c++14", "-std=c++14", quoted),
                                 (":c++11", "-std=c++11", quoted),
                                 (":c++14-angled", "-std=c++14", angled)]
                tag = "" if len(srcs) == len(all_srcs) else f"-{srcs[0].split('.')[0]}"
                for suffix, extra, incs in variants:
                    yield (f"compile:{lang}:{rel}{tag}{suffix}", dirpath,
                           f'{cc} {flags} {force} {incs} -idirafter "{SHIMS}" {extra} '
                           f"-o engine_bin {names} -lm -lpthread")


def new_mach_o_binaries(root, since):
    """Executable Mach-O files under root that appeared after `since`."""
    found = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "CMakeFiles")]
        for name in files:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            if not st.st_mode & 0o111 or st.st_size < 20000 or st.st_mtime < since:
                continue
            if os.path.splitext(name)[1].lower() in (
                    ".sh", ".py", ".pl", ".bat", ".o", ".a", ".dylib", ".txt",
                    ".rs", ".go", ".d", ".pas"):
                continue
            with open(path, "rb") as f:
                if f.read(4) not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    continue
            found.append((st.st_size, path))
    found.sort(reverse=True)
    return [p for _, p in found]


def speaks_uci(path, log):
    """Send `uci` and look for a reply.

    stdin is held open for a moment: engines that answer from a worker thread
    print nothing at all if `quit` arrives in the same write.
    """
    try:
        proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=os.path.dirname(path))
    except OSError as exc:
        log.write(f"could not start {path}: {exc}\n")
        return False, ""
    stdin = proc.stdin
    assert stdin is not None
    try:
        stdin.write("uci\n")
        stdin.flush()
        time.sleep(3)
        try:
            stdin.write("quit\n")
            stdin.flush()
        except OSError:
            pass
        out = proc.communicate(timeout=25)[0] or ""
    except subprocess.TimeoutExpired:
        proc.kill()
        out = proc.communicate()[0] or ""
    except Exception as exc:                                  # noqa: BLE001
        proc.kill()
        log.write(f"uci probe failed for {path}: {exc}\n")
        return False, ""
    log.write(f"--- uci probe of {os.path.basename(path)}\n{out[:1500]}\n")
    name = next((line[8:].strip() for line in out.splitlines()
                 if line.startswith("id name")), "")
    return ("uciok" in out or "id name" in out), name


def install(key, folder, exe, built, log):
    """Copy the Linux support files, then the new binary, and ad-hoc sign it."""
    dest = os.path.join(DARWIN_ENGINES, folder)
    os.makedirs(dest, exist_ok=True)

    source_folder = os.path.join(LINUX_ENGINES, folder)
    skip = (".7z", ".zip", ".tar.gz", ".tgz", ".so", ".url", ".exe", ".dll")
    if os.path.isdir(source_folder):
        for dirpath, dirs, files in os.walk(source_folder):
            rel = os.path.relpath(dirpath, source_folder)
            for name in files:
                if name.lower().endswith(skip):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, "rb") as f:
                    if f.read(4) == b"\x7fELF":       # a Linux binary, not for us
                        continue
                target_dir = dest if rel == "." else os.path.join(dest, rel)
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(path, os.path.join(target_dir, name))

    target = os.path.join(dest, exe)
    shutil.copy2(built, target)
    os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # Ad-hoc signature, so Gatekeeper does not kill a freshly built binary.
    run(f'codesign --force --sign - "{target}"', dest, log, timeout=120)
    return target


def which(tool):
    return shutil.which(tool, path=os.path.expanduser("~/.cargo/bin")
                        + ":/opt/homebrew/bin:" + os.environ.get("PATH", ""))


def build_one(key, folder, exe):
    log_path = os.path.join(WORK, "logs", f"{key}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = open(log_path, "w")
    log.write(f"=== {key} -> Engines/{folder}/{exe} ===\n")

    if key in UNSUPPORTED:
        log.write(f"*** not shipped on macOS: {UNSUPPORTED[key]}\n")
        log.close()
        return {"key": key, "ok": False, "reason": f"not shipped: {UNSUPPORTED[key]}"}

    tool = NEEDS_TOOL.get(key)
    if tool and not which(tool):
        log.write(f"*** needs {tool}, which is not installed\n")
        log.close()
        return {"key": key, "ok": False, "reason": f"needs {tool}"}

    root = prepare(key, log)
    if root is None:
        log.write("*** no source archive ships for this engine\n")
        log.close()
        return {"key": key, "ok": False, "reason": "no source archive"}

    since = time.time() - 1
    attempts = 0
    for label, cwd, cmd in strategies(key, root):
        if not os.path.isdir(cwd):
            continue
        attempts += 1
        run(cmd, cwd, log)
        for binary in new_mach_o_binaries(root, since):
            ok, name = speaks_uci(binary, log)
            if ok:
                target = install(key, folder, exe, binary, log)
                log.write(f"*** built via {label} and installed to {target}\n")
                log.close()
                return {"key": key, "ok": True, "how": label,
                        "id_name": name, "installed": os.path.relpath(target, HERE)}
        since = time.time() - 1

    log.write(f"*** no working binary after {attempts} attempts\n")
    log.close()
    return {"key": key, "ok": False, "reason": f"{attempts} strategies failed"}


def show_list(names):
    print(f"{'engine':<15} {'installed as':<28} status")
    print("-" * 62)
    built = missing = 0
    for key in sorted(names):
        folder, exe = names[key]
        path = os.path.join(DARWIN_ENGINES, folder, exe)
        if os.path.isfile(path):
            built += 1
            print(f"{key:<15} {folder + '/' + exe:<28} installed")
        else:
            missing += 1
            has_src = source_archive(key) is not None
            print(f"{key:<15} {folder + '/' + exe:<28} "
                  f"{'not built' if has_src else 'no source archive'}")
    print(f"\n{built} installed, {missing} missing")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("engines", nargs="*", help="engine keys to build (default: all)")
    parser.add_argument("--list", action="store_true",
                        help="show what is installed, build nothing")
    args = parser.parse_args()

    if sys.platform != "darwin":
        sys.exit("BuildEngines.py builds the macOS engines; run it on macOS.")

    names = registry_names()
    if args.list:
        show_list(names)
        return

    os.makedirs(WORK, exist_ok=True)
    os.makedirs(DARWIN_ENGINES, exist_ok=True)
    write_shims()

    keys = args.engines or sorted(names)
    unknown = [k for k in keys if k not in names]
    if unknown:
        sys.exit(f"unknown engine(s): {', '.join(unknown)}")

    results = []
    for i, key in enumerate(keys, 1):
        folder, exe = names[key]
        print(f"[{i}/{len(keys)}] {key} ... ", end="", flush=True)
        result = build_one(key, folder, exe)
        print(f"ok ({result['how']})" if result["ok"] else f"skipped: {result['reason']}",
              flush=True)
        results.append(result)

    report = os.path.join(WORK, "report.json")
    previous = {}
    if os.path.isfile(report):
        previous = {r["key"]: r for r in json.load(open(report))}
    previous.update({r["key"]: r for r in results})
    with open(report, "w") as f:
        json.dump(sorted(previous.values(), key=lambda r: r["key"]), f, indent=1)

    built = [r for r in results if r["ok"]]
    print(f"\n{len(built)}/{len(results)} engines built. "
          f"Logs in {os.path.relpath(os.path.join(WORK, 'logs'), HERE)}, "
          f"report in {os.path.relpath(report, HERE)}.")


if __name__ == "__main__":
    main()
