from setuptools import setup, find_packages

setup(
    name="origin-or",
    version="1.7.19",
    description="The Origin programming language",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Nikhil Mahankali",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[],
    extras_require={
        "pi": ["RPi.GPIO", "adafruit-circuitpython-servokit", "smbus2"],
        "build": ["pyinstaller"],
    },
    entry_points={
        "console_scripts": [
            "origin=origin.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Interpreters",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
    ],
)
