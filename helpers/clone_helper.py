from mysql_manager.exceptions import PluginsAreNotInstalled
from mysql_manager.instance import Mysql


class CloneHelper:
    @staticmethod
    def get_required_plugins_on_src(src: Mysql, repl: Mysql):
        src_plugins = src.get_plugins()
        repl_plugins = repl.get_plugins()
        return repl_plugins - src_plugins

    @classmethod
    def is_clone_possible(cls, src: Mysql, repl: Mysql):
        required_plugins_on_src = cls.get_required_plugins_on_src(src, repl)
        if required_plugins_on_src:
            raise PluginsAreNotInstalled(
                plugin_names=[
                    plugin.name for plugin in required_plugins_on_src
                ]
            )
