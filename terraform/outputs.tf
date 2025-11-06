output "app_name" {
  description = "Name of the deployed application"
  value       = juju_application.blackbox_exporter.name
}

output "provides" {
  description = "Map of provided integrations"
  value = {
    self_metrics_endpoint = "self-metrics-endpoint"
    grafana_dashboard     = "grafana-dashboard"
  }
}

output "requires" {
  description = "Map of required integrations"
  value = {
    logging   = "logging"
    ingress   = "ingress"
    catalogue = "catalogue"
    probes    = "probes"
  }
}
