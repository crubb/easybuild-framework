# #
# Copyright 2013-2013 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
# #
"""
This describes the easyconfig format version 1.X

This is the original pure python code, to be exec'ed rather then parsed

@author: Stijn De Weirdt (Ghent University)
"""
from distutils.version import LooseVersion

from easybuild.framework.easyconfig.format.format import EasyConfigFormatConfigObj


class FormatOneZero(EasyConfigFormatConfigObj):
    """Simple extension of FormatOne with configparser blocks
        Deprecates setting version and toolchain/toolchain version in FormatOne
    """
    VERSION = LooseVersion('1.0')
