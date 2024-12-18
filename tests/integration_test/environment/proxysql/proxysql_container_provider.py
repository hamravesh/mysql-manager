import os
from testcontainers.core.container import DockerContainer, Network
from tests.integration_test.environment.component_provider import ComponentProvider


class ProxysqlContainerProvider(ComponentProvider):
    def __init__(self,
        name: str,
        network: Network,
        image: str,
        local_username: str,
        local_password: str,
        remote_username: str,
        remote_password: str,
        config: str
    ) -> None:
        super().__init__(
            name=name,
            network=network,
            image=image,
            component=DockerContainer
        )
        self.local_username = local_username
        self.local_password = local_password
        self.remote_username = remote_username
        self.remote_password = remote_password
        self.config = config

    def _write_config(self) -> str:
        config_path = "/tmp/configs/proxysql/proxysql.cnf"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.writelines(self.config)
        return config_path

    def setup(self):
        super().setup()
        config_path = self._write_config()
        self.component.with_volume_mapping(
            host=config_path,
            container="/etc/proxysql.cnf"
        )
