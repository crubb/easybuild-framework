##
# Copyright 2009-2012 Stijn De Weirdt
# Copyright 2010 Dries Verdegem
# Copyright 2010-2012 Kenneth Hoste
# Copyright 2011 Pieter De Baets
# Copyright 2011-2012 Jens Timmerman
#
# This file is part of EasyBuild,
# originally created by the HPC team of the University of Ghent (http://ugent.be/hpc).
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
##
"""
EasyBuild support for building and installing WIEN2k, implemented as an easyblock
"""

import fileinput
import os
import re
import shutil
import sys
import tempfile
from distutils.version import LooseVersion

import easybuild.tools.environment as env
import easybuild.tools.toolkit as toolkit
from easybuild.framework.application import Application
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.filetools import run_cmd, run_cmd_qa, unpack
from easybuild.tools.modules import get_software_version


class EB_WIEN2k(Application):
    """Support for building/installing WIEN2k."""

    def __init__(self,*args,**kwargs):
        """Enable building in install dir."""
        Application.__init__(self, *args, **kwargs)

        self.build_in_installdir = True

    @staticmethod
    def extra_options():
        testdata_urls = ["http://www.wien2k.at/reg_user/benchmark/test_case.tar.gz",
                         "http://www.wien2k.at/reg_user/benchmark/mpi-benchmark.tar.gz"]

        extra_vars = [
                      ('runtest', [True, "Run WIEN2k tests (default: True).", CUSTOM]),
                      ('testdata', [testdata_urls, "URL for test data required to run WIEN2k benchmark test (default: %s)." % testdata_urls, CUSTOM])
                     ]
        return Application.extra_options(extra_vars)

    def unpack_src(self):
        """Unpack WIEN2k sources using gunzip and provided expand_lapw script."""
        Application.unpack_src(self)

        cmd = "gunzip *gz"
        run_cmd(cmd, log_all=True, simple=True)

        cmd = "./expand_lapw"
        qanda = {'continue (y/n)': 'y'}
        no_qa = [
                 'tar -xf.*',
                 '.*copied and linked.*'
                 ]

        run_cmd_qa(cmd, qanda, no_qa=no_qa, log_all=True, simple=True)
    
    def configure(self):
        """Configure WIEN2k build by patching siteconfig_lapw script and running it."""

        self.cfgscript = "siteconfig_lapw"

        # patch config file first

        # toolkit-dependent values
        comp_answer = None
        if self.toolkit().comp_family() == toolkit.INTEL:
            if LooseVersion(get_software_version("icc")) >= LooseVersion("2011"):
                comp_answer = 'I'  # Linux (Intel ifort 12.0 compiler + mkl )
            else:
                comp_answer = "K1"  # Linux (Intel ifort 11.1 compiler + mkl )

        elif self.toolkit().comp_family() == toolkit.GCC:
            comp_answer = 'V'  # Linux (gfortran compiler + gotolib)

        else:
            self.log.error("Failed to determine toolkit-dependent answers.")

        # libraries
        rlibs = "%s %s" % (os.getenv('LIBLAPACK_MT'), self.toolkit().get_openmp_flag())
        rplibs = "%s %s" % (os.getenv('LIBSCALAPACK_MT'), os.getenv('LIBLAPACK_MT'))

        # add FFTW libs if needed
        fftwfullver = get_software_version('FFTW')
        if fftwfullver:
            fftwver = ""
            if LooseVersion(fftwfullver) >= LooseVersion('3'):
                fftwver = fftwfullver.split('.')[0]
            rplibs += " -lfftw%(fftwver)s_mpi -lfftw%(fftwver)s" % {'fftwver': fftwver}

        d = {
             'FC': '%s %s'%(os.getenv('F90'), os.getenv('FFLAGS')),
             'MPF': "%s %s"%(os.getenv('MPIF90'), os.getenv('FFLAGS')),
             'CC': os.getenv('CC'),
             'LDFLAGS': '$(FOPT) %s ' % os.getenv('LDFLAGS'),
             'R_LIBS': rlibs,  # libraries for 'real' (not 'complex') binary
             'RP_LIBS' :rplibs,  # libraries for 'real' parallel binary
             'MPIRUN': ''
            }

        for line in fileinput.input(self.cfgscript, inplace=1, backup='.orig'):
            # set config parameters
            for (k,v) in d.items():
                regexp = re.compile('^([a-z0-9]+):%s:.*' % k)
                res = regexp.search(line)
                if res:
                    # we need to exclude the lines with 'current', otherwise we break the script
                    if not res.group(1) == "current":
                        line = regexp.sub('\\1:%s:%s' % (k, v), line)
            # avoid exit code > 0 at end of configuration
            line = re.sub('(\s+)exit 1', '\\1exit 0', line)
            sys.stdout.write(line)

        # set correct compilers
        os.putenv('bin', os.getcwd())

        dc = {
              'COMPILERC': os.getenv('CC'),
              'COMPILER': os.getenv('F90'),
              'COMPILERP': os.getenv('MPIF90'),
             }

        for (k,v) in dc.items():
            f = open(k,"w")
            f.write(v)
            f.close()

        # configure with patched configure script
        self.log.debug('%s part I (configure)' % self.cfgscript)

        cmd = "./%s" % self.cfgscript
        qanda = {
                 'Press RETURN to continue': '',
                 'compiler) Selection:': comp_answer,
                 'Your compiler:': '',
                 'Hit Enter to continue': '',
                 'Shared Memory Architecture? (y/n):': 'n',
                 'Remote shell (default is ssh) =': '',
                 'and you need to know details about your installed  mpi ..) (y/n)': 'y',
                 'Recommended setting for parallel f90 compiler: mpiifort ' \
                        'Current selection: Your compiler:': os.getenv('MPIF90'),
                 'Q to quit Selection:': 'Q',
                 'A Compile all programs (suggested) Q Quit Selection:': 'Q',
                 ' Please enter the full path of the perl program: ': '',
                 'continue or stop (c/s)': 'c',
                 '(like taskset -c). Enter N / your_specific_command:': 'N',
                 'If you are using mpi2 set MPI_REMOTE to 0  Set MPI_REMOTE to 0 / 1:': '0',
                 'Do you have MPI and Scalapack installed and intend to run ' \
                    'finegrained parallel? (This is usefull only for BIG cases ' \
                    '(50 atoms and more / unit cell) and you need to know details ' \
                    'about your installed  mpi and fftw ) (y/n)': 'y',
                }

        no_qa = [
                 'You have the following mkl libraries in %s :' % os.getenv('MKLROOT'),
                 "%s[ \t]*.*"%os.getenv('MPIF90'),
                 "%s[ \t]*.*"%os.getenv('F90'),
                 "%s[ \t]*.*"%os.getenv('CC'),
                 ".*SRC_.*"
                 ]

        std_qa = {
                  r'S\s+Save and Quit[\s\n]+To change an item select option.[\s\n]+Selection:': 'S',
                 }

        run_cmd_qa(cmd, qanda, no_qa=no_qa, std_qa=std_qa, log_all=True, simple=True)

    def make(self):
        """Build WIEN2k by running siteconfig_lapw script again."""

        self.log.debug('%s part II (make)' % self.cfgscript)

        cmd = "./%s" % self.cfgscript

        qanda = {
                 'L Perl path (if not in /usr/bin/perl) Q Quit Selection:': 'R',
                 'A Compile all programs S Select program Q Quit Selection:': 'A',
                 'Press RETURN to continue': '\nQ', # also answer on first qanda pattern with 'Q' to quit
                 ' Please enter the full path of the perl program: ':''}
        no_qa = [
                 "%s[ \t]*.*" % os.getenv('MPIF90'),
                 "%s[ \t]*.*" % os.getenv('F90'),
                 "%s[ \t]*.*" % os.getenv('CC'),
                 ".*SRC_.*",
                 ".*: warning .*"
                 ]
    
        self.log.debug("no_qa for %s: %s" % (cmd, no_qa))
        run_cmd_qa(cmd, qanda, no_qa=no_qa, log_all=True, simple=True)

    def test(self):
        """Run WPS test (requires large dataset to be downloaded). """

        def run_wien2k_test(cmd_arg):
            """Run a WPS command, and check for success."""

            cmd = "x_lapw lapw1 %s" % cmd_arg
            (out, _) = run_cmd(cmd, log_all=True, simple=False)

            re_success = re.compile("LAPW1\s+END")
            if not re_success.search(out):
                self.log.error("Test '%s' in %s failed (pattern '%s' not found)?" % (cmd, os.getcwd(),
                                                                                     re_success.pattern))
            else:
                self.log.info("Test '%s' seems to have run successfully: %s" % (cmd, out))

        if self.getcfg('runtest'):
            if not self.getcfg('testdata'):
                self.log.error("List of URLs for testdata not provided.")

            path = os.getenv('PATH')
            env.set('PATH', "%s:%s" % (self.installdir, path))

            try:
                cwd = os.getcwd()

                # create temporary directory
                tmpdir = tempfile.mkdtemp()
                os.chdir(tmpdir)

                # download data
                testdata_paths = {}
                for testdata in self.getcfg('testdata'):
                    td_path = self.file_locate(testdata)
                    if not td_path:
                        self.log.error("Downloading file from %s failed?" % testdata)
                    testdata_paths.update({os.path.basename(testdata): td_path})

                self.log.debug('testdata_paths: %s' % testdata_paths)

                # unpack serial benchmark
                serial_test_name = "test_case"
                unpack(testdata_paths['%s.tar.gz' % serial_test_name], tmpdir)

                # run serial benchmark
                os.chdir(os.path.join(tmpdir, serial_test_name))
                run_wien2k_test("-c")

                # unpack parallel benchmark (in serial benchmark dir)
                parallel_test_name = "mpi-benchmark"
                unpack(testdata_paths['%s.tar.gz' % parallel_test_name], tmpdir)

                # run parallel benchmark
                os.chdir(os.path.join(tmpdir, serial_test_name))
                run_wien2k_test("-p")

                os.chdir(cwd)
                shutil.rmtree(tmpdir)

            except OSError, err:
                self.log.error("Failed to run WIEN2k benchmark tests: %s" % err)

            # reset original path
            env.set('PATH', path)

            self.log.debug("Current dir: %s" % os.getcwd())

    def make_install(self):
        """Fix broken symlinks after build/installation."""
        # fix broken symlink
        os.remove(os.path.join(self.installdir, "SRC_w2web", "htdocs", "usersguide"))
        os.symlink(os.path.join(self.installdir, "SRC_usersguide_html"),
                   os.path.join(self.installdir, "SRC_w2web","htdocs", "usersguide"))

    def sanitycheck(self):
        """Custom sanity check for WIEN2k."""

        if not self.getcfg('sanityCheckPaths'):
            lapwfiles = []
            for suffix in ["0","0_mpi","1","1_mpi","1c","1c_mpi","2","2_mpi","2c","2c_mpi",
                           "3","3c","5","5c","7","7c","dm","dmc","so"]:
                p = os.path.join(self.installdir, "lapw%s" % suffix)
                lapwfiles.append(p)

            self.setcfg('sanityCheckPaths',{'files': lapwfiles,
                                            'dirs':[]
                                           })

            self.log.info("Customized sanity check paths: %s" % self.getcfg('sanityCheckPaths'))

        Application.sanitycheck(self)

    def make_module_extra(self):
        """Set WIENROOT environment variable, and correctly prepend PATH."""

        txt = Application.make_module_extra(self)

        txt += self.moduleGenerator.setEnvironment("WIENROOT", "$root")
        txt += self.moduleGenerator.prependPaths("PATH", "$root")

        return txt
