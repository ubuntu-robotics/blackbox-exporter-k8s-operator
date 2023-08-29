#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""A Juju charm for Blackbox Exporter."""

import logging
import socket
from types import SimpleNamespace
from urllib.parse import urlparse

from blackbox import WorkloadManager
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from ops.charm import ActionEvent, CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    WaitingStatus,
)
from ops.pebble import PathError, ProtocolError

logger = logging.getLogger(__name__)


class BlackboxExporterCharm(CharmBase):
    """A Juju charm for Blackbox Exporter."""

    # Container name must match metadata.yaml
    # Service name matches charm name for consistency
    _container_name = _service_name = "blackbox-exporter"
    _relations = SimpleNamespace()  # TODO: is this needed?
    _port = 9115

    # path, inside the workload container, to the blackbox exporter configuration files
    _config_path = "/etc/blackbox-exporter/blackbox-exporter.yaml"

    def __init__(self, *args):
        super().__init__(*args)

        self.container = self.unit.get_container(self._container_name)

        # Core lifecycle events
        self.blackbox_workload = WorkloadManager(
            self,
            container_name=self._container_name,
            port=self._port,
            web_external_url=self._external_url,
            config_path=self._config_path,
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        self.framework.observe(
            # The workload manager too observes pebble ready, but still need this here because
            # of the common exit hook (otherwise would need to pass the common exit hook as
            # a callback).
            self.on.blackbox_exporter_pebble_ready,  # pyright: ignore
            self._on_pebble_ready,
        )
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

        # Action events
        self.framework.observe(
            self.on.show_config_action, self._on_show_config_action  # pyright: ignore
        )

        # Libraries
        # - Kubernetes resource patch
        self.resources_patch = KubernetesComputeResourcesPatch(
            self,
            self._container_name,
            resource_reqs_func=self._resource_reqs_from_config,
        )
        self.framework.observe(
            self.resources_patch.on.patch_failed,  # pyright: ignore
            self._on_k8s_patch_failed,
        )

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        """Get the resources requirements from the Juju config."""
        limits = {
            "cpu": self.model.config.get("cpu"),
            "memory": self.model.config.get("memory"),
        }
        requests = {"cpu": "0.25", "memory": "200Mi"}
        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)

    def _on_k8s_patch_failed(self, event: K8sResourcePatchFailedEvent):
        self.unit.status = BlockedStatus(str(event.message))

    def _on_show_config_action(self, event: ActionEvent):
        """Hook for the show-config action."""
        event.log(f"Fetching {self._config_path}")
        if not self.blackbox_workload.is_ready:
            event.fail("Container not ready")
        try:
            content = self.container.pull(self._config_path)
            event.set_results(
                {
                    "path": self._config_path,
                    "content": str(content.read()),
                }
            )
        except (ProtocolError, PathError) as e:
            event.fail(str(e))

    def _common_exit_hook(self) -> None:
        """Event processing hook that is common to all events to ensure idempotency."""
        if not self.resources_patch.is_ready():
            if isinstance(self.unit.status, ActiveStatus) or self.unit.status.message == "":
                self.unit.status = WaitingStatus("Waiting for resource limit patch to apply")
            return

        if not self.container.can_connect():
            self.unit.status = MaintenanceStatus("Waiting for pod startup to complete")
            return

        # Make sure the external url is valid
        if external_url := self._external_url:
            parsed = urlparse(external_url)
            if not (parsed.scheme in ["http"] and parsed.hostname):
                # This shouldn't happen
                logger.error(
                    "Invalid external url: %s; must include scheme and hostname.",
                    external_url,
                )
                self.unit.status = BlockedStatus(
                    f"Invalid external url: '{external_url}'; must include scheme and hostname."
                )
                return

        # Update config file
        self.blackbox_workload.update_config()

        # Update pebble layer
        self.blackbox_workload.update_layer()

        # Reload or restart the service
        self.blackbox_workload.reload()

        self.unit.status = ActiveStatus()

    @property
    def _internal_url(self) -> str:
        """Return the fqdn dns-based in-cluster (private) address of the blackbox exporter."""
        return f"http://{socket.getfqdn()}:{self._port}"

    @property
    def _external_url(self) -> str:
        """Return the externally-reachable (public) address of the blackbox exporter.

        If not set in the config, return the internal url.
        """
        return self.model.config.get("web-external-url") or self._internal_url

    def _on_pebble_ready(self, _):
        """Event handler for PebbleReadyEvent."""
        self._common_exit_hook()

    def _on_config_changed(self, _):
        """Event handler for ConfigChangedEvent."""
        self._common_exit_hook()

    def _on_update_status(self, _):
        """Event handler for UpdateStatusEvent."""
        self._common_exit_hook()

    def _on_upgrade_charm(self, _):
        """Event handler for replica's UpgradeCharmEvent."""
        # After upgrade (refresh), the unit ip address is not guaranteed to remain the same, and
        # the config may need update. Calling the common hook to update.
        self._common_exit_hook()


if __name__ == "__main__":
    main(BlackboxExporterCharm)
