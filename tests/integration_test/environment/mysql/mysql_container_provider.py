import os
import tempfile
from typing import Union
from testcontainers.core.container import Network
from testcontainers.mysql import MySqlContainer
from tests.integration_test.environment.component_provider import ComponentProvider


class MysqlContainerProvider(ComponentProvider):
    def __init__(self,
        name: str,
        server_id: int,
        network: Network,
        image: str, 
        config: str,
        root_username: str = "root",
        root_password: str = "root",
    ) -> None:
        super().__init__(
            name=name,
            network=network,
            image=image,
            component=MySqlContainer,
            component_kwargs={
                "username": root_username,
                "password": root_password
            }
        )
        self.root_username = root_username
        self.root_password = root_password
        self.server_id = server_id
        self.config = config
    
    def _write_config(self) -> str:
        config_path = f"/tmp/configs/mysql/mysql_{self.server_id}.cnf"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.writelines(self.config)
        return config_path
    
    def setup(self):
        super().setup()
        config_path = self._write_config()
        self.component.with_volume_mapping(
            host=config_path,
            container="/etc/mysql/conf.d/mysql.cnf"
        )
