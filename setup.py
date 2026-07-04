import os
import shutil
from setuptools import setup, find_packages

# Monkeypatch copystat, os.link, chmod, and utime to avoid "Operation not permitted" errors under WSL mounts
try:
    if hasattr(os, 'link'):
        del os.link
        
    orig_chmod = os.chmod
    def patched_chmod(path, mode, *args, **kwargs):
        try:
            orig_chmod(path, mode, *args, **kwargs)
        except OSError:
            pass
    os.chmod = patched_chmod

    orig_utime = os.utime
    def patched_utime(path, times=None, *args, **kwargs):
        try:
            orig_utime(path, times, *args, **kwargs)
        except OSError:
            pass
    os.utime = patched_utime

    orig_copystat = shutil.copystat
    def patched_copystat(src, dst, *args, **kwargs):
        try:
            orig_copystat(src, dst, *args, **kwargs)
        except OSError:
            pass
    shutil.copystat = patched_copystat
except Exception:
    pass

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
    version="1.0.22",
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
