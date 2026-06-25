import os
from setuptools import setup, find_packages

# Read the contents of README.md
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

# Read the contents of requirements.txt
requirements_path = os.path.join(this_directory, "requirements.txt")
install_requires = []
if os.path.exists(requirements_path):
    with open(requirements_path, encoding="utf-8") as f:
        install_requires = [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

setup(
    name="gitcast",
    version="1.0.0",
    description="git diff → published post. under 60 seconds.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Timilehin Agoro",
    author_email="agorotimilehi05@gmail.com",
    url="https://github.com/drizzy765/gitcast",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "gitcast=cli.gitcast:main",
        ],
    },
    include_package_data=True,
    install_requires=install_requires,
)
