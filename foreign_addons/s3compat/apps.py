from addon_toolkit.interfaces.foreign_addon_config import ForeignAddonConfig

from .imp import S3CompatStorageImp


class S3CompatForeignAddonConfig(ForeignAddonConfig):
    name = "foreign_addons.s3compat"
    verbose_name = "S3 Compatible Storage"
    default = True

    @property
    def imp(self):
        return S3CompatStorageImp

    @property
    def addon_name(self):
        return "S3COMPAT"
