import os
import random
import string
import sys
import tempfile

from fabric.api import *

import pantheon


def _drush_download(modules):
    """ Download list of modules using Drush.
    modules: list of module names.

    """
    #TODO: temporary until integrated in pantheon repo
    for module in modules:
         local('drush -y dl %s' % module)


class InstallTools:
    """ Generic Drupal installation helper functions.
    
    """

    def __init__(self, project):
        """ Initialize generic installation object & helper functions.
        project: the name of the project to be built.

        """
        self.server = pantheon.PantheonServer()

        self.project = project
        self.db_password = pantheon.random_string(10)
        self.working_dir = tempfile.mkdtemp()
        self.destination = os.path.join(self.server.webroot, project)


    def build_project_branch(self):
        """ Bring master up to date and create a new project branch.

        """
        with cd('/var/git/projects'):
            local('git checkout master')
            local('git pull')
            with settings(hide('warnings'), warn_only=True):
                local('git tag -d %s.initialization' % self.project)
                local('git branch -D %s' % self.project)
            local('git branch %s' % self.project)


    def build_working_dir(self):
        """ Clone project to a temporary working directory.

        """
        local('git clone -l /var/git/projects -b %s %s' % (self.project, 
                                                           self.working_dir))


    def build_project_modules(self, modules=['apachesolr','memcache','varnish']):
        """ Add required modules to project branch.
        modules: Optional list of modules. Defaults to:
                 apachesolr, memcache, varnish

        """
        #TODO: temporary until integrated in pantheon repo.
        module_dir = os.path.join(self.working_dir, 'sites/all/modules')
        local('mkdir %s' % module_dir)
        with cd(module_dir):
            _drush_download(modules)
        with cd(self.working_dir):
            local('git add -A .')
            local("git commit -m 'Add required modules'")


    def build_project_libraries(self):
       """ Add code libraries to project.

       """ 
       #TODO: temporary until integrated in pantheon repo
       dest = os.path.join(self.working_dir, 'sites/all/modules/apachesolr/')
       with cd(dest):
           local('wget http://solr-php-client.googlecode.com/files/SolrPhpClient.r22.2009-11-09.tgz')
           local('tar xzf SolrPhpClient.r22.2009-11-09.tgz')
           local('rm -f SolrPhpClient.r22.2009-11-09.tgz')
       with cd(self.working_dir):
           local('git add -A .')
           local("git commit -m 'Add required libraries'")


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
            local("git commit -m 'Site from makefile'")
        local('rm -rf %s' % tempdir)


    def build_file_dirs(self, dirs=['sites/default/files']):
        """ Creates files directory within the Drupal installation.
        dirs: List. Optional: list of file directories to create.
              Defaults to ['sites/default/files'].
              All paths are relative to Drupal installation.

        """
        for file_dir in dirs:
            path = os.path.join(self.working_dir, file_dir)
            local("mkdir -p %s " % path)
            with open('%s/.gitignore' % path, 'a') as f:
                f.write('*\n')
                f.write('!.gitignore\n')


    def build_settings_file(self, site='default'):
        """ Create settings.php and pantheon.settings.php
        Site: Optional. The drupal site name. Defaults to 'default'.

        """
        site_dir = os.path.join(self.working_dir, 'sites/%s/' % (site))
        local("cp %s %s" % (site_dir + 'default.settings.php', site_dir + 'settings.php'))
        pantheon.create_pantheon_settings_file(site_dir)


    def build_database(self, environments=pantheon.get_environments()):
        """ Create a new database and set user grants (all).

        """
        username = self.project
        password = self.db_password

        for env in environments:      
            database = '%s_%s' % (self.project, env)
            local("mysql -u root -e 'DROP DATABASE IF EXISTS %s'" % (database))
            local("mysql -u root -e 'CREATE DATABASE IF NOT EXISTS %s'" % (database))
            local("mysql -u root -e \"GRANT ALL ON %s.* TO '%s'@'localhost' \
                                      IDENTIFIED BY '%s';\"" % (database,
                                                                username, 
                                                                password))


    def build_drush_alias(self, environments=pantheon.get_environments()):
        """ Create drush aliases for each environment in a project.
        environments: Optional. List.

        """
        for env in environments:
            vhost = self.server.get_vhost_file(self.project, env)
            root = os.path.join(self.server.webroot, self.project, env)
            drush_dict = {'project': self.project,
                          'environment': env,
                          'vhost_path': vhost,
                          'root': root}
            self.server.create_drush_alias(drush_dict)


    def build_solr_index(self, environments=pantheon.get_environments()):
        """ Create solr index for each environment in a project.
        environments: Optional. List.

        """
        for env in environments:
            self.server.create_solr_index(self.project, env)


    def build_vhost(self, environments=pantheon.get_environments()):
        """ Create vhost files for each environment in a project.
        environments: Optional. List. 

        """
        for env in environments:

            vhost_dict = {'project': self.project,
                          'environment': env,
                          'db_name': '%s_%s' % (self.project, env),
                          'db_username':self.project,
                          'db_password':self.db_password,
                          'solr_path': '/%s_%s' % (self.project, env),
                          'memcache_prefix': '%s_%s' % (self.project, env)}

            filename = '%s_%s' % (self.project, env)
            if env == 'live': 
                filename = '000_' + filename

            self.server.create_vhost(filename, vhost_dict)
            if self.server.distro == 'ubuntu':
               local('a2ensite %s' % filename)


    def build_drupal_cron(self, environments=pantheon.get_environments()):
        """ Create drupal cron jobs in hudson for each development environment.
        environments: Optional. List.

        """
        for env in environments:
            self.server.create_drupal_cron(self.project, env)


    def build_environments(self, tag='initialization', environments=pantheon.get_environments()):
       """ Clone project from central repo to all environments.
           environments: Optional. List.

       """ 
       local('rm -rf %s' % (os.path.join(self.server.webroot, self.project)))
       for env in environments:
           destination = os.path.join(self.server.webroot, self.project, env)
           local('git clone -l /var/git/projects -b %s %s' % (self.project, 
                                                              destination))

           with cd(destination):
               if env == 'dev':
                   local('git checkout master')
                   local('git checkout %s' % self.project)
               else:
                   local('git fetch')
                   local('git reset --hard %s.%s' % (self.project, tag))
                

    def build_permissions(self, environments=pantheon.get_environments()):
        """ Set permissions on project directory, settings.php, and files dir.
        environments: Optional. List.

        """
        with cd(self.server.webroot):
            local('chown -R root:%s %s' % (self.server.web_group, self.project))

        for env in environments:
            site_dir = os.path.join(self.server.webroot, \
                                    '%s/%s/sites/default' % (self.project, env))
            with cd(site_dir):
                local('chown %s:%s settings.php' % (self.server.web_group, 
                                                    self.server.web_group))
                local('chmod 660 settings.php')
                local('chmod 440 pantheon.settings.php')
                local('chmod 770 files')
        

    def push_to_repo(self, tag='initialization'):
        """ Commit changes in working directory and push to central repo.

        """
        with cd(self.working_dir):
            local('git checkout %s' % self.project)
            local('git add -A .')
            local("git commit -m 'Initialize Project: %s'" % self.project)
            local('git tag %s.%s' % (self.project, tag))
            local('git push')
            local('git push --tags')


    def cleanup(self):
        """ Remove working directory.

        """
        local('rm -rf %s' % self.working_dir)

