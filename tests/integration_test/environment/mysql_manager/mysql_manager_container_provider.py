import os
from testcontainers.core.generic import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.network import Network
from tests.integration_test.environment.component_provider import ComponentProvider


class MysqlManagerContainerProvider(ComponentProvider):
    def __init__(self,
        name: str,
        image: str,
        network: Network,
        config: str
    ) -> None:
        super().__init__(
            name=name,
            network=network,
            image=image,
            component=DockerContainer
        )
        self.config = config

    def _write_config(self) -> str:
        config_path = "/tmp/configs/mm/cluster-spec.yaml"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.writelines(self.config)
        return config_path

    def setup(self):
        super().setup()
        config_path = self._write_config()
        self.component.with_volume_mapping(
            host=config_path,
            container="/etc/mm/cluster-spec.yaml"
        )
