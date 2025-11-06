# Terraform module for blackbox-exporter-k8s

This is a Terraform module facilitating the deployment of the `blackbox-exporter-k8s` charm, using the [Terraform juju provider](https://github.com/juju/terraform-provider-juju/). For more information, refer to the provider [documentation](https://registry.terraform.io/providers/juju/juju/latest/docs).

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| juju | ~> 1.0 |

## Providers

| Name | Version |
|------|---------|
| juju | ~> 1.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| juju_application.blackbox_exporter | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| app_name | Name to give the deployed application | `string` | `"blackbox-exporter"` | no |
| channel | Channel that the charm is deployed from | `string` | n/a | yes |
| config | Map of the charm configuration options | `map(string)` | `{}` | no |
| constraints | String listing constraints for this application | `string` | `"arch=amd64"` | no |
| model_uuid | Reference to an existing model resource or data source for the model to deploy to | `string` | n/a | yes |
| revision | Revision number of the charm | `number` | `null` | no |
| storage_directives | Map of storage used by the application, which defaults to 1 GB, allocated by Juju | `map(string)` | `{}` | no |
| units | Unit count/scale | `number` | `1` | no |

## Outputs

| Name | Description |
|------|-------------|
| app_name | Name of the deployed application |
| provides | Map of provided integrations |
| requires | Map of required integrations |

## Example Usage

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "~> 1.0"
    }
  }
}

provider "juju" {}

data "juju_model" "my_model" {
  name  = "my-model"
  owner = "admin"
}

module "blackbox_exporter" {
  source     = "git::https://github.com/canonical/blackbox-exporter-k8s-operator//terraform"
  model_uuid = data.juju_model.my_model.uuid
  channel    = "stable"
  
  config = {
    # Add any configuration options here
  }
}

# To integrate with Prometheus
resource "juju_integration" "blackbox_prometheus" {
  model_uuid = data.juju_model.my_model.uuid

  application {
    name     = module.blackbox_exporter.app_name
    endpoint = module.blackbox_exporter.provides.self_metrics_endpoint
  }

  application {
    name     = "prometheus"
    endpoint = "metrics-endpoint"
  }
}
```
