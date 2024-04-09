#!/usr/bin/env python3

# Build the BeeRef appimage. Run from the git root directory.
# On github actions:
#   ./tools/build_appimage --version=${{ github.ref_name }}\
#      --jsonfile=tools/linux_libs.json
# Locally:
#   ./tools/build_appimage --version=0.3.3-dev --jsonfile=tools/linux_libs.json
#      --skip-apt


import argparse
import json
import logging
import os
import shutil
import subprocess
from urllib.request import urlretrieve


parser = argparse.ArgumentParser(
    description=('Create an appimage for BeeRef. '
                 'Run from the git root directory.'))
parser.add_argument(
    '-v', '--version',
    required=True,
    help='BeeRef version number/tag for output file')
parser.add_argument(
    '-j', '--jsonfile',
    required=True,
    help='Json with lib files and packages as generated by find_linux_libs')
parser.add_argument(
    '--redownload',
    default=False,
    action='store_true',
    help='Re-use downloaded files if present')
parser.add_argument(
    '--skip-apt',
    default=False,
    action='store_true',
    help='Skip apt install step')
parser.add_argument(
    '-l', '--loglevel',
    default='INFO',
    choices=list(logging._nameToLevel.keys()),
    help='log level for console output')

args = parser.parse_args()


BEEVERSION = args.version.removeprefix('v')
APPIMAGE = 'python3.11.8-cp311-cp311-manylinux_2_28_x86_64.AppImage'
PYVER = '3.11'
logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, args.loglevel))


def run_command(*args, capture_output=False):
    logger.info(f'Running command: {args}')
    result = subprocess.run(args, capture_output=capture_output)
    assert result.returncode == 0, f'Failed with exit code {result.returncode}'


def download_file(url, filename):
    if not args.redownload and os.path.exists(filename):
        logger.info(f'Found file: {filename}')
    else:
        logger.info(f'Downloading: {url}')
        logger.info(f'Saving as: {filename}')
        urlretrieve(url, filename=filename)
    os.chmod(filename, 0o755)


url = ('https://github.com/niess/python-appimage/releases/download/'
       f'python{PYVER}/{APPIMAGE}')
download_file(url, filename='python.appimage')


try:
    shutil.rmtree('squashfs-root')
except FileNotFoundError:
    pass
run_command('./python.appimage', '--appimage-extract',
            capture_output=True)

run_command('squashfs-root/usr/bin/pip',
            'install',
            '.',
            f'--target=squashfs-root/opt/python{PYVER}/lib/python{PYVER}/')

logger.info(f'Reading from: {args.jsonfile}')
with open(args.jsonfile, 'r') as f:
    data = json.loads(f.read())
libs = data['libs']
packages = data['packages']
excludes = data['excludes']
paths = set()

if not args.skip_apt:
    run_command('sudo', 'apt', 'install', *packages)

logger.info('Copying .so files to appimage...')

existing_files = []
for root, subdirs, files in os.walk('squashfs-root'):
    existing_files.extend(files)

for lib in libs:
    if os.path.basename(lib) in existing_files:
        logger.debug(f'Skipping {lib} (already in appimage)')
        continue
    if os.path.basename(lib) in excludes:
        logger.debug(f'Skipping {lib} (excluded)')
        continue
    paths.add(os.path.dirname(lib))
    if os.path.exists(lib):
        filename = lib
    else:
        filename, _ = os.path.splitext(lib)
    dest = f'squashfs-root{filename}'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    logger.debug(f'Copying {filename} to {dest}')
    shutil.copyfile(filename, f'squashfs-root{filename}')


logger.info('Writing run script...')
# Adapted from usr/bin/python3.x in the python appimage
os.remove('squashfs-root/AppRun')
# ^ This is only a symlink to usr/bin/python3.x

paths = [
    '/usr/lib',   # The libs that come with the python appimage ar in /usr/lib
] + list(paths)
ld_paths = ['${APPDIR}' + p for p in paths] + ['${LD_LIBRARY_PATH}']
ld_paths = ':'.join(ld_paths)
logger.debug(f'LD_LIBRARY_PATH: {ld_paths}')

content = """#! /bin/bash

# If running from an extracted image, then export ARGV0 and APPDIR
if [ -z "${APPIMAGE}" ]; then
    export ARGV0="$0"

    self=$(readlink -f -- "$0") # Protect spaces (issue 55)
    here="${self%/*}"
    tmp="${here%/*}"
    export APPDIR="${tmp%/*}"
fi

# Resolve the calling command (preserving symbolic links).
export APPIMAGE_COMMAND=$(command -v -- "$ARGV0")

# Export SSL certificate
export SSL_CERT_FILE="${APPDIR}/opt/_internal/certs.pem"
"""
content += f'export LD_LIBRARY_PATH="{ld_paths}"\n'
content += f'"$APPDIR/opt/python{PYVER}/bin/python{PYVER}" -I -m beeref "$@"\n'

with open('squashfs-root/AppRun', 'w') as f:
    f.write(content)
os.chmod('squashfs-root/AppRun', 0o755)

url = ('https://github.com/AppImage/AppImageKit/releases/download/'
       'continuous/appimagetool-x86_64.AppImage')

download_file(url, filename='appimagetool.appimage')
run_command('./appimagetool.appimage',
            'squashfs-root',
            f'BeeRef-{BEEVERSION}.appimage',
            '--no-appstream')
