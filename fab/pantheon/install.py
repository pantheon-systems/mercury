import os
import random
import string
import sys
import tempfile

from fabric.api import *

import pantheon
import project

def _drush_download(modules, destination, version):
    """ Download list of modules using Drush.
    modules: list of module names.
    destination: where to move the module after download
    version: set the default major version

    """
    #TODO: temporary until integrated in pantheon repo
    temp_dir = tempfile.mkdtemp()
    with cd(temp_dir):
        for module in modules:
             with settings(warn_only=True):
                 result = local('drush -by --default-major=%s dl %s' % 
                                (version, module))
             pantheon.log_drush_backend(result)
        local('mv * %s' % destination)
    local('rm -rf %s' % temp_dir)

class InstallTools(project.BuildTools):

    def __init__(self, project, version, **kw):
        """ Initialize generic installation object & helper functions. """
        super(InstallTools, self).__init__()
        self.working_dir = tempfile.mkdtemp()
        self.author = 'Jenkins User <jenkins@pantheon>'
        self.destination = os.path.join(self.server.webroot, self.project)
        self.version = int(version)

    def setup_working_dir(self):
        super(InstallTools, self).setup_working_dir(self.working_dir)

    def setup_database(self):
        """ Create a new database and set user grants. """
        for env in self.environments:
            super(InstallTools, self).setup_database(env, self.db_password)

    def setup_pantheon_modules(self):
        """ Add required modules to project branch. """
        if self.version == 6:
            modules = ['apachesolr','memcache','varnish']
        if self.version == 7:
            modules = ['apachesolr-7.x-1.0-beta3', 'memcache-7.x-1.0-beta3']
        module_dir = os.path.join(self.working_dir, 'sites/all/modules')
        local('mkdir -p %s' % module_dir)
        _drush_download(modules, module_dir, self.version)

    def setup_pantheon_libraries(self):
        super(InstallTools, self).setup_pantheon_libraries(self.working_dir)

    def setup_files_dir(self):
        """ Creates Drupal files directory and sets gitignore for all sub-files

        """
        path = os.path.join(self.working_dir, 'sites/default/files')
        local("mkdir -p %s " % path)
        with open('%s/.gitignore' % path, 'a') as f:
            f.write('*\n')
            f.write('!.gitignore\n')

    def setup_settings_file(self):
        """ Create settings.php and pantheon.settings.php

        """
        site_dir = os.path.join(self.working_dir, 'sites/default')
        super(InstallTools, self).setup_settings_file(site_dir)

    def setup_permissions(self):
        super(InstallTools, self).setup_permissions(handler='install')

    def push_to_repo(self):
        super(InstallTools, self).push_to_repo(tag='initialization')

    def cleanup(self):
        """ Remove working directory.

        """
        local('rm -rf %s' % self.working_dir)

    def build_makefile(self, makefile):
        """ Setup Drupal site using drush make
        makefile: full path to drush makefile

        """
        tempdir = tempfile.mkdtemp()
        local('rm -rf %s' % tempdir)
        local("drush make %s %s" % (makefile, tempdir))
        local('rm -rf %s/*' % self.working_dir)
        local('rsync -av %s/* %s' % (tempdir, self.working_dir))
        with cd(self.working_dir):
            local('git add -A .')
            local("git commit --author=\"%s\" -m 'Site from makefile'" % self.author)
        local('rm -rf %s' % tempdir)

