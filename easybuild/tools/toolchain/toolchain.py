##
# Copyright 2012 Stijn De Weirdt
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
The toolchain module with the abstract Toolchain class and
a set of derived, predefined and tested toolchains.

Creating a new toolchain should be as simple as possible.
"""

from vsc import fancylogger
from easybuild.tools.environment import setenv
from easybuild.tools.modules import Modules, get_software_root, get_software_version
from easybuild.tools.toolchain.options import ToolchainOptions
from easybuild.tools.toolchain.variables import ToolchainVariables
import sys

class Toolchain(object):
    """General toolchain class"""
    OPTIONS_CLASS = ToolchainOptions
    VARIABLES_CLASS = ToolchainVariables

    DUMMY_NAME = 'dummy' ## The official dummy toolchain name
    DUMMY_VERSION = 'dummy'  ## if name==DUMMY_NAME and version==DUMMY_VERSION, do not load dependencies

    NAME = None
    VERSION = None

    #classmethod
    def _is_toolchain_for(cls, name):
        """see if this class can provide support for toolchain named name"""
        ## TODO report later in the initialization the found version
        if hasattr(cls, 'NAME') and name == cls.NAME:
            return True
        elif cls.__name__ == 'name':
            ## classname is also tested
            return True

        return False


    _is_toolchain_for = classmethod(_is_toolchain_for)


    def __init__(self, name=None, version=None):
        self.base_init()

        self.dependencies = []
        self.toolchain_dependencies = []

        if name is None:
            name = self.NAME
        if name is None:
            self.log.raiseException("init: no name provided")
        self.name = name

        if version is None:
            version = self.VERSION
        if version is None:
            self.log.raiseException("init: no version provided")
        self.version = version

        self.opts = None
        self.vars = None

    def base_init(self):
        print sys.modules.keys()
        if not hasattr(self, 'log'):
            self.log = fancylogger.getLogger(self.__class__.__name__)
        else:
            print 'BASEINIT EXISTING', self.log, type(self.log)


        if not hasattr(self, 'options'):
            self.options = self.OPTIONS_CLASS()

        if not hasattr(self, 'variables'):
            self.variables = self.VARIABLES_CLASS()

        print 'BASEINIT', self.log, type(self.log)

    def set_variables(self):
        """Do nothing? Everything should have been set by others
            Needs to be defined for super() relations
        """
        self.log.debug("set_variables: toolchain variables. Do nothing.")

    def generate_vars(self):
        """Convert the variables in simple vars"""
        self.vars = {}
        for k, v in self.variables.items():
            self.vars[k] = str(v)

    def show_variables(self, offset='', sep='\n', verbose=False):
        """Pretty print the variables"""
        if self.vars is None:
            self.generate_vars()

        var_names = self.variables.keys()
        var_names.sort()
        res = []
        for v in var_names:
            res.append("%s=%s" % (v, self.variables[v]))
            if verbose:
                res.append("# type %s" % (type(self.variables[v])))
                res.append("# %s" % (self.variables[v].show_el()))
                res.append("# repr %s" % (self.variables[v].__repr__()))

        if offset is None:
            offset = ''
        txt = sep.join(["%s%s" % (offset, x) for x in res])
        self.log.debug("show_variables:\n%s" % txt)
        return txt

    def get_software_root(self, name):
        """Try to get the software root for name"""
        root = get_software_root(name)
        if root is None:
            self.log.raiseException("get_software_root software root for %s was not found in environment" % (name))
        else:
            self.log.debug("get_software_root software root %s for %s was found in environment" % (root, name))
        return root

    def get_software_version(self, name):
        """Try to get the software root for name"""
        version = get_software_version(name)
        if version is None:
            self.log.raiseException("get_software_version software version for %s was not found in environment" % (name))
        else:
            self.log.debug("get_software_version software version %s for %s was found in environment" % (version, name))

        return version


    def _toolchain_exists(self, name=None, version=None):
        """
        Verify if there exists a toolchain by this name and version
        """
        if not name:
            name = self.name
        if not version:
            version = self.version

        if self.name == self.DUMMY_NAME:
            self.log.debug("_toolchian_exists: checking for %s toolchain. Always exists, returning True" %
                           self.DUMMY_NAME)
            return True

        ## TODO: what about dummy versions ?

        self.log.debug("_toolchain_exists: checking for name %s version %s" % (name, version))
        return Modules().exists(name, version)

    def set_options(self, options):
        """ Process toolchain options """
        for opt in options.keys():
            ## Only process supported opts
            if opt in self.opts:
                self.options[opt] = options[opt]
            else:
                ## used to be warning, but this is a severe error imho
                self.log.raiseException("set_options: undefined toolchain option %s specified (possible names %s)" % (opt, ",".join(self.options.keys())))

    def get_dependency_version(self, dependency):
        """ Generate a version string for a dependency on a module using this toolchain """
        # Add toolchain to version string
        toolchain = ''
        if self.name != self.DUMMY_NAME:
            toolchain = '-%s-%s' % (self.name, self.version)
        elif self.version != self.DUMMY_VERSION:
            toolchain = '%s' % (self.version)

        # Check if dependency is independent of toolchain
        ## TODO: assuming DUMMY_NAME here, what about version?
        if self.DUMMY_NAME in dependency and dependency[self.DUMMY_NAME]:
            toolchain = ''

        suffix = dependency.get('suffix', '')

        if 'version' in dependency:
            version = "".join([dependency['version'], toolchain, suffix])
            self.log.debug("get_dependency_version: version in dependency return %s" % version)
            return version
        else:
            toolchain_suffix = "".join([toolchain, suffix])
            matches = Modules().available(dependency['name'], toolchain_suffix)
            # Find the most recent (or default) one
            if len(matches) > 0:
                version = matches[-1][-1]
                self.log.debug("get_dependency_version: version not in dependency return %s" % version)
                return
            else:
                self.log.raiseException('get_dependency_version: No toolchain version for dependency '\
                                        'name %s (suffix %s) found' % (dependency['name'], toolchain_suffix))

    def add_dependencies(self, dependencies):
        """ Verify if the given dependencies exist and add them """
        mod = Modules()
        self.log.debug("add_dependencies: adding toolchain dependencies %s" % dependencies)
        for dep in dependencies:
            if 'tk' in dep:
                ## TODO LEGACY to be cleaned up
                self.log.raiseException('add_dependencies: legacy tk found in dep %s' % dep)

            if not 'tc' in dep:
                dep['tc'] = self.get_dependency_version(dep)

            if not mod.exists(dep['name'], dep['tc']):
                self.log.raiseException('add_dependencies: no module found for dependency %s/%s' % (dep['name'], dep['tc']))
            else:
                self.dependencies.append(dep)
                self.log.debug('add_dependencies: added toolchain dependency %s' % dep)

    def prepare(self, onlymod=None):
        """
        Prepare a set of environment parameters based on name/version of toolchain
        - load modules for toolchain and dependencies
        - generate extra variables and set them in the environment

        onlymod: Boolean/string to indicate if the toolchain should only load the enviornment
        with module (True) or also set all other variables (False) like compiler CC etc
        (If string: comma separated list of variables that will be ignored).
        """
        if not self._toolchain_exists():
            self.log.raiseException("No module found for toolchain name '%s' (%s)" % (self.name, self.version))

        if self.name == self.DUMMY_NAME:
            if self.version == self.DUMMY_VERSION:
                self.log.info('prepare: toolchain dummy mode, dummy version; not loading dependencies')
            else:
                self.log.info('prepare: toolchain dummy mode and loading dependencies')
                modules = Modules()
                modules.addModule(self.dependencies)
                modules.load()
            return

        ## Load the toolchain and dependencies modules
        modules = Modules()
        modules.addModule([(self.name, self.version)])
        modules.addModule(self.dependencies)
        modules.load()

        ## Determine direct toolchain dependencies, so we can prepare for them
        self.toolchain_deps = modules.dependencies_for(self.name, self.version, depth=0)
        self.log.debug('prepare: list of direct toolchain dependencies: %s' % self.toolchain_deps)

        ## Generate the variables to be set
        self.set_variables()

        ## set the variables
        ## onlymod can be comma-separated string of variables not to be set
        if onlymod == True:
            self.log.debug("prepare: do not set additional variables onlymod=%s" % onlymod)
        else:
            self.log.debug("prepare: set additional variables onlymod=%s" % onlymod)

            ## add LDFLAGS and CPPFLAGS from dependencies to self.vars
            self._add_dependency_variables()
            self._setenv_variables(onlymod)

    def _add_dependency_variables(self, names=None, cpp=None, ld=None):
        """ Add LDFLAGS and CPPFLAGS to the self.variables based on the dependencies
            names should be a list of strings containing the name of the dependency
        """
        cpp_paths = ['include']
        ld_paths = ['lib']
        if not self.options.get('32bit', None):
            ld_paths.insert(0, 'lib64')

        if cpp is not None:
            cpp_paths = cpp + cpp_paths
        if ld is not None:
            ld_paths = ld + ld_paths

        if not names:
            deps = self.dependencies
        else:
            deps = [{'name':name} for name in names if name is not None]

        for dep in deps:
            root = self.get_software_root(dep['name'])
            self.variables.append_subdirs("CPPFLAGS", root, subdirs=cpp_paths)
            self.variables.append_subdirs("LDFLAGS", root, subdirs=ld_paths)

    def _setenv_variables(self, donotset=None):
        """Actually set the environment variables"""
        self.log.debug("_setenv_variables: setting variables: donotset=%s" % donotset)

        donotsetlist = []
        if isinstance(donotset, str):
            ## TODO : more legacy code that should be using proper type
            self.log.raiseException("_setenv_variables: using commas-separated list. should be deprecated.")
            donotsetlist = donotset.split(',')
        elif isinstance(donotset, list):
            donotsetlist = donotset

        for key, val in self.vars.items():
            if key in donotsetlist:
                self.log.debug("_setenv_variables: not setting environment variable %s (value: %s)." % (key, val))
                continue

            self.log.debug("_setenv_variables: setting environment variable %s to %s" % (key, val))
            setenv(key, val)

            # also set unique named variables that can be used in Makefiles
            # - so you can have 'CFLAGS = $(EBVARCFLAGS)'
            # -- 'CLFLAGS = $(CFLAGS)' gives  '*** Recursive variable `CFLAGS'
            # references itself (eventually).  Stop' error
            setenv("EBVAR%s" % key, val)

    ## legacy functions TODO remove after migration
    ## should search'n'replaced
    def get_type(self, name, type_map):
        """Determine type of toolchain based on toolchain dependencies."""
        self.log.raiseException("get_type: legacy code. should not be needed anymore.")

        toolchain_dep_names = [dep['name'] for dep in self.toolchain_deps]

        for req_mods, tc_type in type_map.items():
            match = True
            for req_mod in req_mods:
                if not req_mod in toolchain_dep_names:
                    match = False
            if match:
                return tc_type

        self.log.raiseException("get_type: failed to determine %s based on toolchain dependencies." % name)

    def _set_variables(self, dontset=None):
        """ Sets the environment variables """
        self.log.raiseException("_set_variables: legacy code. use _setenv_variables.")

    def _addDependencyVariables(self, names=None):
        """ Add LDFLAGS and CPPFLAGS to the self.vars based on the dependencies
        names should be a list of strings containing the name of the dependency"""
        self.log.raiseException("_addDependencyVaraibles: legacy code. use _add_dependency_variables.")

    def _setVariables(self, dontset=None):
        """ Sets the environment variables """
        self.log.raiseException("_setVariables: legacy code. use _set_variables.")

    def _toolkitExists(self, name=None, version=None):
        """
        Verify if there exists a toolkit by this name and version
        """
        self.log.raiseException("_toolchainExists: legacy code. replace use _toolchain_exists.")

    def mpi_type(self):
        """Determine type of MPI library based on toolkit dependencies."""
        self.log.raiseException("mpi_type: legacy code. use mympirun.")

    def mpi_cmd_for(self, cmd, nr_ranks):
        """Construct an MPI command for the given command and number of ranks."""
        self.log.raiseException("mpi_cmd_for: legacy code. use mympirun.")

