#!/usr/bin/env python

from setuptools import setup

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = ["aiohttp"]

setup_requirements = ["pytest-runner"]

test_requirements = [
    "asynctest",
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "wheel",
]

setup(
    name="iaqualink",
    version="0.3.3",
    description="Asynchronous library for Jandy iAqualink",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Florent Thoumie",
    author_email="florent@thoumie.net",
    url="https://github.com/flz/iaqualink-py",
    packages=["iaqualink"],
    package_dir={"iaqualink": "src/iaqualink"},
    include_package_data=True,
    install_requires=requirements,
    license="BSD",
    keywords="iaqualink",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    test_suite="tests",
    tests_require=test_requirements,
    setup_requires=setup_requirements,
    python_requires=">=3.5",
)
