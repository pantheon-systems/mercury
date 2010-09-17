from pantheon import siteinstall
import pdb

def install_site(project='pantheon', profile='pantheon'):
    """ Create a new Drupal installation.
    project: Installation namespace.
    profile: The installation type (e.g. pantheon/openatrium)

    """
    #If additional values are needed in the installation profile classes,
    #they can be placed in init_dict or build_dict and will be passed to
    #the profile object (and ignored by existing profile classes).
    init_dict = {'profile':profile,
                 'project':project}

    build_dict = {}

    handler = get_handler(**init_dict)
    handler.build(**build_dict)


def get_handler(profile, **kw):
    """ Return instantiated profile object.
        profile: name of the installation profile.

    """
    profiles = {'pantheon':_PantheonProfile,
                'openatrium':_OpenAtriumProfile,
                'openpublish':_OpenPublishProfile}

    # If handler doesn't exist, use pantheon
    return profiles.has_key(profile) and \
           profiles[profile](**kw) or \
           profiles['pantheon'](**kw)


"""
To define additional profile handlers:
     1. Create a new profile class (example below)
     2. Add the profile name & class name to the profiles dict in get_handler().
     Example profile handler:

class MIRProfile(siteinstall.InstallTools):
    def __init__(self, project, **kw):
        siteinstall.InstallTools.__init__(self, project, **kw)

    def build(self, **kw):
        # Step 1: create a working installation
        # Step 2: ??? 
        # Step 3: Make it rain.
"""

class _PantheonProfile(siteinstall.InstallTools):
    """ Default Pantheon Installation Profile.
    
    """

    def __init__(self, project, **kw):
        siteinstall.InstallTools.__init__(self, project, **kw)
  

    def build(self, **kw):
        makefile = '/opt/pantheon/fabric/templates/pantheon.make'

        self.build_pantheon_core()
        self.build_makefile(makefile)
        self.build_file_dirs()
        self.build_gitignore()
        pdb.set_trace()
        self.build_default_settings_file()
        self.build_database()
        self.build_solr_index()
        self.build_vhost()
        self.build_drupal_cron()
        self.build_pantheon_settings_file()
        self.build_permissions()
        self.build_from_repo()
        self.commit('')

class _OpenAtriumProfile(siteinstall.InstallTools):
    """ Open Atrium Installation Profile.

    """
    def __init__(project, **kw):
        siteinstall.InstallTools.__init__(self, project, **kw)
  

    def build(self, **kw):
        pass


class _OpenPublishProfile(siteinstall.InstallTools):
    """ Open Publish Installation Profile.

    """
    def __init__(project, **kw):
        siteinstall.InstallTools.__init__(self, project, **kw)
  

    def build(self, **kw):
        pass
