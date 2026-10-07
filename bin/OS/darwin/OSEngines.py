"""Engine registry for macOS.

Derived from OS/linux/OSEngines.py. Only a subset of the engines shipped for
Linux and Windows can be built for macOS (many are distributed as prebuilt
x86-64 binaries with no macOS/arm64 upstream), so every entry below is
registered only when its executable is actually present in Engines/. Building
an engine into Engines/<key>/ is therefore all that is needed to enable it.

Version strings say what the binary built from the shipped source reports, which
for a number of engines is a different point release than the prebuilt Linux
binary. The elo values are the ones measured for that Linux build and are
carried over unchanged, so for those engines they are an approximation.
"""

import os
import stat

import FasterCode

from Code.Base.Constantes import ENG_INTERNAL
from Code.Engines import Engines
from Code.Z import Util


def read_engines(folder_engines):
    dic_engines = {}

    def mas(clave, autor, version, url, exe, elo, folder=None, nodes_compatible=None):
        if folder is None:
            folder = clave
        path_exe = Util.opj(folder_engines, folder, exe)
        engine = Engines.Engine(
            clave,
            autor,
            version,
            url,
            path_exe,
        )
        engine.set_type(ENG_INTERNAL)
        engine.elo = elo
        engine.set_uci_option("Log", "false")
        engine.set_uci_option("Ponder", "false")
        engine.set_uci_option("Hash", "16")
        engine.set_uci_option("Threads", "1")
        # An engine that has not been built for macOS is silently left out, but
        # the object is still returned so the caller can keep configuring it.
        if os.path.isfile(path_exe):
            if not os.access(path_exe, os.X_OK):
                os.chmod(path_exe, os.stat(path_exe).st_mode | stat.S_IXUSR)
            dic_engines[clave] = engine
        if nodes_compatible is not None:
            engine.set_nodes_compatible(nodes_compatible)
        # engine.read_uci_options()
        return engine

    bmi2 = "-bmi2" if FasterCode.is_bmi2() else ""

    levels = list(range(1100, 2000, 100)) + [2200]
    for level in levels:
        cm = mas(
            f"maia-{level}",
            "Reid McIlroy-Young,Ashton Anderson,Siddhartha Sen,Jon Kleinberg,Russell Wang + LcZero team",
            str(level),
            "https://www.maiachess.com/",
            "Lc0-0.27.0",
            level,
            folder="maia",
            nodes_compatible=True,
        )
        cm.set_uci_option("WeightsFile", f"maia-{level}.pb.gz")
        cm.path_exe = Util.relative_path(Util.opj(folder_engines, "maia", "Lc0-0.27.0"))
        cm.name = f"Maia-{level}"
        cm.set_nodes_maia(level)

    cm = mas(
        "lc0",
        "The LCZero Authors",
        "0.32.0",
        "https://github.com/LeelaChessZero",
        "Lc0-0.32.0",
        3332,
        nodes_compatible=True,
    )
    cm.set_uci_option("Hash", "64")
    cm.set_uci_option("Threads", "2")
    cm.set_multipv(10, 500)

    cm = mas(
        "stockfish",
        "Tord Romstad, Marco Costalba, Joona Kiiski",
        "18",
        "https://stockfishchess.org/",
        "stockfish-18-64",
        3700,
    )
    cm.set_uci_option("Hash", "64")
    cm.set_uci_option("Threads", "2")
    cm.set_multipv(10, 256)

    avx2 = "-avx2" if bmi2 else ""
    cm = mas(
        "komodo",
        "Don Dailey, Larry Kaufman, Mark Lefler, Dmitry Pervov, Dietrich Kappe",
        f"dragon-1{avx2}",
        "https://komodochess.com/",
        f"dragon-linux{avx2}",
        3529,
        nodes_compatible=True,
    )
    cm.set_uci_option("Hash", "64")
    cm.set_uci_option("Threads", "2")
    cm.set_multipv(10, 218)
    cm.name = "Dragon-1"

    mas("alouette", "Roland Chastain", "0.1.7", "https://codeberg.org/rchastain/alouette", "alouette64", 800)

    mas(
        "amoeba",
        "Richard Delorme",
        "3.3.1",
        "https://github.com/abulmo/amoeba",
        "Amoeba-2.6",
        2911,
        nodes_compatible=True,
    )

    mas("andscacs", "Daniel José Queraltó", "0.95", "https://www.andscacs.com/", "Andscacs-0.95", 3240)

    mas("arasan", "Jon Dart", "22.2", "https://www.arasanchess.org/", "Arasan-22.2", 3259)

    mas(
        "asymptote",
        "Maximilian Lupke",
        "0.8",
        "https://github.com/malu/asymptote",
        "Asymptote-0.8",
        2909,
        nodes_compatible=True,
    )

    mas("beef", "Jonathan Tseng", "0.36", "https://github.com/jtseng20/Beef", "Beef-0.36", 3097)

    mas(
        "cassandre",
        "Jean-Francois Romang), Raphael Grundrich, Thomas Adolph, Chad Koch",
        "0.24",
        "https://sourceforge.net/projects/cassandre/",
        "Cassandre-0.24",
        1140,
    )

    mas("ceechess", "Tom Reinitz", "1.3", "https://github.com/bctboi23/CeeChess", "CeeChess-1.3.2", 2268)

    mas("cheng", "Martin Sedlák", "4.40", "https://www.vlasak.biz/cheng", "Cheng-4.40", 2750)

    mas("cinnamon", "Giuseppe Cannella", "1.2b", "https://cinnamonchess.altervista.org/", "Cinnamon-1.2b", 1930)

    mas("chessika", "Laurent Chea", "2.21", "https://gitlab.com/MrPingouin/chessika", "Chessika-2.21", 1441)

    cm = mas(
        "clarabit", "Salvador Pallares Bejarano", "1.00", "https://sites.google.com/site/sapabe/", "Clarabit-1.00", 2058
    )
    cm.set_uci_option("OwnBook", "false")

    mas(
        "counter",
        "Vadim Chizhov",
        "dev",
        "https://github.com/ChizhovVadim/CounterGo",
        "Counter-3.7",
        2963,
        nodes_compatible=True,
    )

    mas("critter", "Richard Vida", "1.6a", "https://www.vlasak.biz/critter", "Critter-1.6a", 3091)

    mas("ct800", "Rasmus Althoff", "1.46", "https://www.ct800.net/", "CT800_V1.46", 2600, nodes_compatible=True)

    mas(
        "daydreamer",
        "Aaron Becker",
        "1.75 JA",
        "https://github.com/AaronBecker/daydreamer",
        "Daydreamer-1.75",
        2670,
        nodes_compatible=True,
    )

    mas("delocto", "Moritz Terink", "0.6", "https://github.com/moterink/Delocto", "Delocto-0.61n", 2625)

    mas(
        "discocheck",
        "Lucas Braesch",
        "5.2.1",
        "https://github.com/lucasart/",
        "Discocheck-5.2.1",
        2700,
        nodes_compatible=True,
    )

    # dragontooth is deliberately not registered on macOS. The version that
    # builds from the shipped source (0.3) answers only "go wtime/btime"; it
    # rejects "go depth" and "go movetime" with "Unknown go subcommand" and then
    # never returns a bestmove, which hangs the GUI in most play modes.

    mas(
        "drofa",
        "Rhys Rustad-Elliott and Alexander Litov",
        "3.3.0",
        "https://github.com/justNo4b/Drofa",
        "Drofa-3.3.0",
        2642,
    )

    mas(
        "ethereal",
        "Andrew Grant, Alayan & Laldon",
        "12.90",
        "https://github.com/AndyGrant/Ethereal",
        "Ethereal-12.75",
        3392,
    )

    mas("eguzkilore", "Lucas Monge", "1.0", "", "eguzkilore", 1000)
    mas("eguzki", "Lucas Monge", "1.0", "", "eguzki", 1500)

    mas(
        "fractal",
        "Visan Alexandru",
        "1.0",
        "https://github.com/visanalexandru/FracTal-ChessEngine",
        "FracTal-1.0",
        2010,
    )

    mas("fruit", "Fabien Letouzey", "2.1", "https://www.fruitchess.com/", "Fruit-2.1", 2784)

    cm = mas(
        "gambitfruit",
        "Ryan Benitez, Thomas Gaksch and Fabien Letouzey",
        "1.0 Beta 4bx",
        "https://github.com/lazydroid/gambit-fruit",
        "gfruit",
        2750,
    )
    cm.name = "Gambit-fruit"

    mas(
        "gaviota",
        "Miguel Ballicora",
        "0.84",
        "https://sites.google.com/site/gaviotachessengine/Home",
        "Gaviota-0.84",
        2638,
        nodes_compatible=True,
    )

    mas("glaurung", "Tord RomsTad", "2.2", "https://www.glaurungchess.com/", "Glaurung-2.2", 2765,
        nodes_compatible=True)

    cm = mas(
        "godel",
        "Juan Manuel Vazquez",
        "7.0",
        "https://sites.google.com/site/godelchessengine",
        "Godel-7.0",
        2979,
        nodes_compatible=True,
    )
    cm.name = "Gödel 7.0"

    mas(
        "goldfish",
        "Bendik Samseth",
        "1.13.0",
        "https://github.com/bsamseth/Goldfish",
        "Goldfish-1.13.0",
        2050,
        nodes_compatible=True,
    )

    mas(
        "greko",
        "Vladimir Medvedev",
        "2020.03",
        "https://greko.su/index_en.html",
        "GreKo-2020.03",
        2580,
        nodes_compatible=True,
    )

    mas(
        "greko98",
        "Vladimir Medvedev",
        "9.8",
        "https://sourceforge.net/projects/greko",
        "GreKo98a",
        2500,
        nodes_compatible=True,
    )

    mas("gunborg", "Torbjorn Nilsson", "1.65", "https://github.com/torgnil/gunborg", "Gunborg-1.35", 2086)

    mas("hactar", "Jost Triller", "0.9.05", "https://github.com/tsoj/hactar", "Hactar-0.9.0", 1421)

    mas(
        "igel",
        "Volodymyr Shcherbyna",
        "3.0.10",
        "https://github.com/vshcherbyna/igel/",
        "Igel-3.0.10",
        3402,
        nodes_compatible=True,
    )

    mas("irina", "Lucas Monge", "0.23", "https://github.com/lukasmonk/irina", "irina", 1600)

    mas("jabba", "Richard Allbert", "1.0", "https://jabbachess.blogspot.com/", "Jabba-1.0", 2078)

    mas("k2", "Sergey Meus", "0.99", "https://github.com/serg-meus/k2", "K2-0.99", 2704, nodes_compatible=True)

    mas(
        "laser",
        "Jeffrey An and Michael An",
        "1.7",
        "https://github.com/jeffreyan11/laser-chess-engine",
        "Laser-1.17",
        3227,
    )

    mas(
        "marvin",
        "Martin Danielsson",
        "5.0.0",
        "https://github.com/bmdanielsson/marvin-chess",
        "Marvin-5.0.0",
        3112,
        nodes_compatible=True,
    )

    mas(
        "monolith",
        "Jonas Mayr",
        "2",
        "https://github.com/cimarronOST/Monolith",
        "Monolith-2.01",
        3003,
        nodes_compatible=True,
    )

    mas(
        "monochrome",
        "Dan Ravensloft, formerly Matthew Brades (England), Manik Charan (India), George Koskeridis, Robert Taylor",
        "",
        "https://github.com/cpirc/Monochrome",
        "Monochrome",
        1601,
    )

    mas("octochess", "Tim Kosse", "r5190", "https://octochess.org/", "Octochess-r5190", 2771)  # New build

    mas("patricia", "Adam Kulju", "4.0", "https://github.com/Adam-Kulju/Patricia", "patricia_4_v2", 3500)

    mas("pawny", "Mincho Georgiev", "0.3.1", "https://pawny.netii.net/", "Pawny-1.2", 2550)

    mas("pigeon", "Stuart Riffle", "1.5.1", "https://github.com/StuartRiffle/pigeon", "Pigeon-1.5.1", 1836)

    mas(
        "pulse",
        "Phokham Nonava",
        "2.0.0",
        "https://github.com/fluxroot/pulse",
        "Pulse-1.6.1",
        1615,
        nodes_compatible=True,
    )

    mas("quokka", "Matt Palmer", "2.1", "https://github.com/mattbruv/Quokka", "Quokka-2.1", 1448)  # New build

    mas(
        "rocinante",
        "Antonio Torrecillas",
        "2.0",
        "https://sites.google.com/site/barajandotrebejos/",
        "Rocinante-2.0",
        1800,
    )

    mas(
        "rodentii",
        "Pawel Koziol",
        "0.9.64",
        "https://www.pkoziol.cal24.pl/rodent/rodent.htm",
        "RodentII-0.9.64",
        2912,
        nodes_compatible=True,
    )

    mas(
        "shallow-blue",
        "Rhys Rustad-Elliott",
        "2.0.0",
        "https://github.com/GunshipPenguin/shallow-blue",
        "Shallow-blue-2.0.0",
        1712,
    )

    mas(
        "simplex",
        "Antonio Torrecillas",
        "0.98",
        "https://sites.google.com/site/barajandotrebejos",
        "Simplex-0.9.8",
        2396,
    )

    # sissa is deliberately not registered on macOS. It compiles and answers UCI,
    # but the search does not work: it reports depth 30 after ~600 nodes, misses
    # a mate in 1, and behaves identically at -O0, so it is not an optimizer
    # artefact. Shipping it would put a nonsense opponent in the engine list.

    mas("spacedog", "Eric Silverman", "0.97.7", "https://github.com/thorsilver/SpaceDog", "SpaceDog-0.97.7", 2231)

    mas("stash", "Morgan Houppin", "30.2", "https://gitlab.com/mhouppin/stash-bot", "Stash-29.0", 3065)

    mas(
        "supernova",
        "Minkai Yang",
        "2.3",
        "https://github.com/MichaeltheCoder7/Supernova",
        "Supernova-2.3",
        2646,
        nodes_compatible=True,
    )

    mas("teki", "Manik Charan", "2", "https://github.com/Mk-Chan/Teki", "Teki-2", 2439)

    mas("texel", "Peter Österlund", "1.08", "https://github.com/peterosterlund2/texel", "texel64", 3100)

    cm = mas(
        "toga",
        "WHMoweryJr,Thomas Gaksch,Fabien Letouzey",
        "deepTogaNPS 1.9.6",
        "https://www.computerchess.info/tdbb/phpBB3/viewtopic.php?f=9&t=357",
        "DeepToga1.9.6nps",
        2843,
    )
    cm.set_multipv(10, 40)
    cm.name = "DeepToga1.9.6nps"

    mas(
        "tucano",
        "Alcides Schulz",
        "9.13",
        "https://sites.google.com/site/tucanochess",
        "Tucano-9.00",
        2940,
        nodes_compatible=True,
    )

    mas("tunguska", "Fernando Tenorio", "1.0", "https://github.com/fernandotenorio/Tunguska", "Tunguska-1.1", 2439)

    mas("velvet", "Martin Honert", "1.2.0", "https://github.com/mhonert/velvet-chess", "Velvet-1.2.0", 2686)

    mas("weiss", "Terje Kirstihagen", "1.3-dev", "https://github.com/TerjeKir/weiss", "Weiss-1.2", 2982)

    mas("wowl", "Eric Yip", "1.3.7", "https://github.com/eric-ycw/wowl", "Wowl-1.3.7", 1925, nodes_compatible=True)

    mas("wyldchess", "Manik Charan", "1.51", "https://github.com/Mk-Chan/WyldChess", "WyldChess-1.51", 2682)

    mas("zappa", "Anthony Cozzie", "1.1", "https://www.acoz.net/zappa/", "Zappa-1.1", 2614, nodes_compatible=True)

    mas("zurichess", "Alexandru Mosoi", "nidwalden", "https://bitbucket.org/zurichess/zurichess/", "Zurichess-1.7.4", 2830)

    return dic_engines


# Engines that support UCI_LimitStrength / UCI_Elo, with the elo range each one
# covers. Callers index read_engines() with these keys, so an engine that was not
# built for macOS has to drop out of the list too.
_LI_FIXED_ELO = (
        ("stockfish", 1400, 3100),
        ("arasan", 1000, 2600),
        ("cheng", 800, 2500),
        ("greko", 1600, 2400),
        ("texel", 700, 2500),
        ("eguzki", 1000, 2700),
        ("ct800", 1000, 2500),
)


def li_engines_fixed_elo() -> tuple:
    folder_engines = Util.opj(os.path.dirname(os.path.abspath(__file__)), "Engines")
    available = read_engines(folder_engines)
    return tuple(x for x in _LI_FIXED_ELO if x[0] in available)
