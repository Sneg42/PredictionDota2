class Patch:
    def getCurrentPatch(self):
        patch = '&patch=7.19&patch=7.18&patch=7.17&patch=7.16&patch=7.15'
        old_patch_from688  = ('&patch=7.14&patch=7.13&patch=7.12&patch=7.11&patch=7.10&patch=7.09&patch=7.08'+ 
                             '&patch=7.07&patch=7.06&patch=7.05&patch=7.04&patch=7.03&patch=7.02&patch=7.01'+
                             '&patch=7.00&patch=6.88')
        return patch + old_patch_from688