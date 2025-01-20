"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name="reboundpy",
    version="0.0.1",
    description="",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aaroncouch/ReboundPy",
    author="Aaron Couch",
    author_email="aaronscouch@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="ncaa, websockets, stats, basketball",
    package_dir={"": "reboundpy"},
    packages=find_packages(where="reboundpy"),
    python_requires=">=3.10, <4",
    install_requires=["requests>=2.32.3", "websockets>=14.1"],
    extras_require={
        "dev": [],
        "test": [],
    },
    package_data={
    },
    data_files=[],
    entry_points={  # Optional
        "console_scripts": [
            "reboundpy=entrypoint.main:main",
        ],
    },
    project_urls={  # Optional
        "Bug Reports": "https://github.com/aaroncouch/ReboundPy/issues",
        "Source": "https://github.com/aaroncouch/ReboundPy",
    },
)