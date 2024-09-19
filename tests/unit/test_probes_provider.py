# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import unittest
from typing import List

from charms.blackbox_k8s.v0.blackbox_probes import BlackboxProbesProvider
from cosl import JujuTopology
from helpers import patch_network_get
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.testing import Harness

RELATION_NAME = "blackbox-probes"

PROVIDER_META = f"""
name: provider-tester
containers:
  blackbox-tester:
provides:
  {RELATION_NAME}:
    interface: blackbox_probes
"""


PROBES: List[dict] = [
    {
        "job_name": "my-first-job",
        "disallowed_key": "irrelavent_value",
        "params": {"module": ["http_2xx"]},
        "static_configs": [
            {
                "targets": ["10.1.238.1"],
                "labels": {"some_key": "some-value"},
            }
        ],
    },
    {
        "job_name": "my-second-job",
        "params": {
            "module": ["icmp"],
        },
        "static_configs": [
            {"targets": ["10.1.238.1"], "labels": {"some_other_key": "some-other-value"}}
        ],
    },
]

MODULES: dict = {
    "http_2xx_longer_timeout": {
        "prober": "http",
        "timeout": "30s",
    }
}


class BlackboxProbesProviderCharmWithModules(CharmBase):
    _stored = StoredState()

    def __init__(self, *args, **kwargs):
        super().__init__(*args)

        self.provider = BlackboxProbesProvider(self, probes=PROBES, modules=MODULES)


class BlackboxProbesProviderTest(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(BlackboxProbesProviderCharmWithModules, meta=PROVIDER_META)
        self.harness.set_model_name("MyUUID")
        self.addCleanup(self.harness.cleanup)
        self.harness.set_leader(True)
        self.harness.begin()

    @patch_network_get()
    def test_provider_sets_scrape_metadata(self):
        rel_id = self.harness.add_relation(RELATION_NAME, "provider")
        self.harness.add_relation_unit(rel_id, "provider/0")

        self.harness.charm.provider.set_probes_spec()

        data = self.harness.get_relation_data(rel_id, self.harness.model.app.name)
        self.assertIn("scrape_metadata", data)
        scrape_metadata = data["scrape_metadata"]
        self.assertIn("model", scrape_metadata)
        self.assertIn("model_uuid", scrape_metadata)
        self.assertIn("application", scrape_metadata)

    @patch_network_get()
    def test_provider_sets_probes_on_relation_joined(self):
        rel_id = self.harness.add_relation(RELATION_NAME, "provider")
        self.harness.add_relation_unit(rel_id, "provider/0")

        self.harness.charm.provider.set_probes_spec()

        data = self.harness.get_relation_data(rel_id, self.harness.model.app.name)
        self.assertIn("scrape_probes", data)
        scrape_data = json.loads(data["scrape_probes"])
        self.assertEqual(scrape_data[0]["static_configs"][0]["targets"], ["10.1.238.1"])
        self.assertEqual(scrape_data[0]["params"]["module"], ["http_2xx"])

    @patch_network_get()
    def test_provider_sets_modules_with_prefix_on_relation_joined(self):
        rel_id = self.harness.add_relation(RELATION_NAME, "provider")
        self.harness.add_relation_unit(rel_id, "provider/0")

        self.harness.charm.provider.set_probes_spec()

        data = self.harness.get_relation_data(rel_id, self.harness.model.app.name)
        self.assertIn("scrape_modules", data)

        scrape_modules = json.loads(data["scrape_modules"])

        topology = JujuTopology.from_dict(json.loads(data["scrape_metadata"]))
        module_name_prefix = "juju_{}_".format(topology.identifier)

        self.assertIn(f"{module_name_prefix}http_2xx_longer_timeout", scrape_modules)

    @patch_network_get()
    def test_provider_prefixes_jobs(self):
        rel_id = self.harness.add_relation(RELATION_NAME, "provider")
        self.harness.add_relation_unit(rel_id, "provider/0")

        self.harness.charm.provider.set_probes_spec()

        data = self.harness.get_relation_data(rel_id, self.harness.model.app.name)
        scrape_data = json.loads(data["scrape_probes"])
        topology = JujuTopology.from_dict(json.loads(data["scrape_metadata"]))
        module_name_prefix = "juju_{}_".format(topology.identifier)

        self.assertEqual(scrape_data[0]["job_name"], f"{module_name_prefix}my-first-job")
