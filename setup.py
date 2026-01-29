"""
TXR Automation Package Setup
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="txr-automation",
    version="1.0.0",
    author="Transaction Reporting Team",
    description="Transaction reporting automation suite",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            # Replay scripts
            "replay-phase2=replay.phase_2_processor:main",
            "replay-phase3=replay.phase_3_processor:main",
            "replay-phase3-final=replay.phase_3_final_lookup:main",
            "replay-xlsx-converter=utils.xlsx_csv_converter:main",
            # Accuracy testing scripts
            "validate-buyer=accuracy_testing.scripts.buyer_id_validation:main",
            "validate-seller=accuracy_testing.scripts.seller_id_validation:main",
            "validate-inconsistent-buyer=accuracy_testing.scripts.inconsistent_buyer_id_validation:main",
            "validate-inconsistent-seller=accuracy_testing.scripts.inconsistent_seller_id_validation:main",
            "validate-pricing=accuracy_testing.scripts.pricing_validation:main",
            "generate-sql-extract=accuracy_testing.scripts.sql_extract_generator:main",
            "generate-accuracy-template=accuracy_testing.scripts.accuracy_template_generator:main",
            "collate-csv-extracts=accuracy_testing.scripts.collate_csv_extracts:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
