# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os.path
import tempfile
from urllib.error import URLError
from urllib import request

from PyQt5 import QtGui

import piexif

logger = logging.getLogger(__name__)


def exif_rotated_image(path=None):
    """Returns a QImage that is transformed according to the source's
    orientation EXIF data.
    """

    img = QtGui.QImage(path)
    if img.isNull():
        return img

    try:
        exif_dict = piexif.load(path)
    except:
        logger.exception(f'Exif parser failed on image: {path}')
        return img

    if piexif.ImageIFD.Orientation in exif_dict['0th']:
        orientation = exif_dict['0th'][piexif.ImageIFD.Orientation]
    else:
        return img

    transform = QtGui.QTransform()

    if orientation == 2:
        return img.mirrored(horizontal=True, vertical=False)
    if orientation == 3:
        transform.rotate(180)
        return img.transformed(transform)
    if orientation == 4:
        return img.mirrored(horizontal=False, vertical=True)
    if orientation == 5:
        transform.rotate(90)
        return img.transformed(transform).mirrored(
            horizontal=True, vertical=False)
    if orientation == 6:
        transform.rotate(90)
        return img.transformed(transform)
    if orientation == 7:
        transform.rotate(270)
        return img.transformed(transform).mirrored(
            horizontal=True, vertical=False)
    if orientation == 8:
        transform.rotate(270)
        return img.transformed(transform)

    return img


def load_image(path):
    if isinstance(path, str):
        path = os.path.normpath(path)
        return (exif_rotated_image(path), path)
    if path.isLocalFile():
        path = os.path.normpath(path.toLocalFile())
        return (exif_rotated_image(path), path)

    img = exif_rotated_image()
    try:
        imgdata = request.urlopen(path.url()).read()
    except URLError as e:
        logger.debug(f'Downloading image failed: {e.reason}')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            fname = os.path.join(tmp, 'img')
            with open(fname, 'wb') as f:
                f.write(imgdata)
                logger.debug(f'Temporarily saved in: {fname}')
            img = exif_rotated_image(fname)
    return (img, path.url())
