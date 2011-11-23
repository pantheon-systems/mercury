# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import tempfile

from fabric.api import *

import update
from pantheon import pantheon

def initialize(vps=None, bcfg2_host='config.getpantheon.com'):
    '''Initialize the Pantheon system.'''
    server = pantheon.PantheonServer()
    server.bcfg2_host = bcfg2_host

    _initialize_fabric()
    _initialize_root_certificate()
    _initialize_package_manager(server)
    _initialize_bcfg2(server)
    _initialize_iptables(server)
    _initialize_drush()
    _initialize_solr(server)
    _initialize_sudoers(server)
    _initialize_acl(server)
    _initialize_jenkins(server)
    _initialize_apache(server)

def init():
    '''Alias of "initialize"'''
    initialize()

def _initialize_fabric():
    """Make symlink of /usr/bin/fab -> /usr/local/bin/fab.

    This is because using pip to install fabric will install it to
    /usr/local/bin but we want to maintain compatibility with existing
    servers and jenkins jobs.

    """
    if not os.path.exists('/usr/bin/fab'):
        local('ln -s /usr/local/bin/fab /usr/bin/fab')

def _initialize_root_certificate():
    """Install the Pantheon root certificate.

    """
    pantheon.configure_root_certificate('http://pki.getpantheon.com')

def _initialize_package_manager(server):
    """Setup package repos and version preferences.

    """
    if server.distro == 'ubuntu':
        with cd(server.template_dir):
            local('cp apt.pantheon.list /etc/apt/sources.list.d/pantheon.list')

            local('cp apt.openssh.pin /etc/apt/preferences.d/openssh')
            local('apt-key add apt.ppakeys.txt')
        	local('echo \'APT::Install-Recommends "0";\' >>  /etc/apt/apt.conf')
			local('echo \'APT::Cache-Limit "20000000";\' >>  /etc/apt/apt.conf')

    elif server.distro == 'centos':
        local('rpm -Uvh http://dl.iuscommunity.org/pub/ius/stable/Redhat/' + \
              '5/x86_64/ius-release-1.0-6.ius.el5.noarch.rpm')
        local('rpm -Uvh http://yum.fourkitchens.com/pub/centos/' + \
              '5/noarch/fourkitchens-release-5-6.noarch.rpm')
        local('rpm --import http://pkg.jenkins-ci.org/redhat/jenkins-ci.org.key')
        local('wget -O /etc/yum.repos.d/jenkins.repo http://pkg.jenkins-ci.org/redhat/jenkins.repo')
        local('yum -y install git17 --enablerepo=ius-testing')
        arch = local('uname -m').rstrip('\n')
        if (arch == "x86_64"):
            exclude_arch = "*.i?86"
        elif (arch == "i386" or arch == "i586" or arch == "i686"):
            exclude_arch = "*.x86_64"
        if exclude_arch:
            local('echo "exclude=%s" >> /etc/yum.conf' % exclude_arch)

    # Update package metadata and download packages.
    server.update_packages()

def _initialize_bcfg2(server):
    """Install bcfg2 client and run for the first time.

    """
    if server.distro == 'ubuntu':
        local('apt-get install -y gamin python-gamin python-genshi bcfg2')
    elif server.distro == 'centos':
        local('yum -y install bcfg2 gamin gamin-python python-genshi ' + \
              'python-ssl python-lxml libxslt')
    template = pantheon.get_template('bcfg2.conf')
    bcfg2_conf = pantheon.build_template(template, {"bcfg2_host": server.bcfg2_host})
    with open('/etc/bcfg2.conf', 'w') as f:
        f.write(bcfg2_conf)

    # We use our own key/certs.
    local('rm -f /etc/bcfg2.key bcfg2.crt')
    # Run bcfg2
    local('/usr/sbin/bcfg2 -vqed', capture=False)

def _initialize_iptables(server):
    """Create iptable rules from template.

    """
    local('/sbin/iptables-restore < /etc/pantheon/templates/iptables')
    if server.distro == 'centos':
        local('cp /etc/pantheon/templates/iptables /etc/sysconfig/iptables')
        local('chkconfig iptables on')
        local('service iptables start')
    else:
        local('cp /etc/pantheon/templates/iptables /etc/iptables.rules')

def _initialize_drush():
    """Install Drush and Drush-Make.

    """
    with cd('/opt'):
        local('[ ! -d drush ] || rm -rf drush')
        local('git clone http://git.drupal.org/project/drush.git')
        with cd('drush'):
            local('git checkout tags/7.x-4.4')
        local('chmod 555 drush/drush')
        local('chown -R root: drush')
        local('mkdir -p /opt/drush/aliases')
        local('ln -sf /opt/drush/drush /usr/local/bin/drush')
        local('drush dl -y --default-major=6 drush_make')
        with open('/opt/drush/.gitignore', 'w') as f:
            f.write('.gitignore\naliases')

def _initialize_solr(server=pantheon.PantheonServer()):
    """Download Apache Solr.

    """
    temp_dir = tempfile.mkdtemp()
    with cd(temp_dir):
        local('wget http://apache.osuosl.org/lucene/solr/1.4.1/apache-solr-1.4.1.tgz')
        local('tar xvzf apache-solr-1.4.1.tgz')
        local('mkdir -p /var/solr')
        local('mv apache-solr-1.4.1/dist/apache-solr-1.4.1.war /var/solr/solr.war')
        local('chown -R ' + server.tomcat_owner + ':root /var/solr/')
    local('rm -rf ' + temp_dir)

def _initialize_sudoers(server):
    """Create placeholder sudoers files. Used for custom sudoer setup.

    """
    local('touch /etc/sudoers.d/003_pantheon_extra')
    local('chmod 0440 /etc/sudoers.d/003_pantheon_extra')

def _initialize_acl(server):
    """Allow the use of ACLs and ensure they remain after reboot.

    """
    local('sudo tune2fs -o acl /dev/sda1')
    local('sudo mount -o remount,acl /')
    # For after restarts
    local('sudo sed -i "s/noatime /noatime,acl /g" /etc/fstab')

def _initialize_jenkins(server):
    """Add a Jenkins user and grant it access to the directory that will contain the certificate.

    """
    # Create the user if it doesn't exist:
    with settings(warn_only=True):
        local('adduser --system --home /var/lib/jenkins --no-create-home --ingroup nogroup --disabled-password --shell /bin/bash jenkins')

    local('usermod -aG ssl-cert jenkins')
    local('apt-get install -y jenkins')

    # Grant it access:
    #local('setfacl --recursive --no-mask --modify user:jenkins:rx /etc/pantheon')
    #local('setfacl --recursive --modify default:user:jenkins:rx /etc/pantheon')

    # Review the permissions:
    #local('getfacl /etc/pantheon', capture=False)

def _initialize_apache(server):
    """Remove the default vhost and clear /var/www.

    """
    if server.distro == 'ubuntu':
        local('a2dissite default')
        local('rm -f /etc/apache2/sites-available/default*')
        local('rm -f /var/www/*')
