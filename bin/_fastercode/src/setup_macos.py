import os

from setuptools import Extension, setup
from Cython.Build import cythonize

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

extensions = [
    Extension(
        name="FasterCode",
        sources=["FasterCode.pyx"],
        libraries=["irina"],
        library_dirs=[BASE_DIR],
        include_dirs=[os.path.join(BASE_DIR, "irina")],
        extra_compile_args=["-O2", "-DNDEBUG", "-fno-strict-aliasing"],
        language="c",
    )
]

setup(
    name="FasterCode",
    version="1.0.0",
    description="Cython bindings for the Irina chess engine (macOS)",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "initializedcheck": False,
            "cdivision": True,
        },
        annotate=False,
    ),
    zip_safe=False,
)
