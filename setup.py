"""
TXR Replay Core Library Setup
"""

from setuptools import setup, find_packages

with open("txr_replay_core/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="txr-replay-core",
    version="1.0.0",
    author="Transaction Reporting Team",
    description="Shared utilities and core functionality for transaction replay processing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
