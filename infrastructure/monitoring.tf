# Monitoring and Security Configuration

# Cloud Monitoring Alert Policies
resource "google_monitoring_alert_policy" "api_errors" {
  display_name = "M&A API Error Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "API Error Rate > 5%"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"4xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "service_down" {
  display_name = "M&A Service Down Alert"
  combiner     = "OR"

  conditions {
    display_name = "Service Unavailable"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\""
      duration        = "600s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
}

# Cloud Armor Security Policy
resource "google_compute_security_policy" "ma_security_policy" {
  name = "ma-security-policy"

  rule {
    action   = "allow"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule"
  }

  rule {
    action   = "deny(403)"
    priority = "2000"
    match {
      expr {
        expression = "request.headers['x-api-key'].size() == 0"
      }
    }
    description = "Block requests without API key"
  }

  rule {
    action   = "rate_based_ban"
    priority = "3000"
    match {
      expr {
        expression = "request.method == 'POST'"
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 100
        interval_sec = 60
      }
    }
    description = "Rate limiting for POST requests"
  }
}

# VPC Service Controls
resource "google_access_context_manager_service_perimeter" "ma_perimeter" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.ma_policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.ma_policy.name}/servicePerimeters/ma_perimeter"
  title  = "M&A Analysis Perimeter"

  status {
    restricted_services = [
      "storage.googleapis.com",
      "bigquery.googleapis.com",
      "run.googleapis.com"
    ]

    resources = [
      "projects/${var.project_id}"
    ]

    access_levels = [
      google_access_context_manager_access_level.ma_access_level.name
    ]
  }
}

resource "google_access_context_manager_access_policy" "ma_policy" {
  parent = "organizations/${var.organization_id}"
  title  = "M&A Analysis Access Policy"
}

resource "google_access_context_manager_access_level" "ma_access_level" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.ma_policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.ma_policy.name}/accessLevels/ma_access_level"
  title  = "M&A Access Level"

  basic {
    conditions {
      ip_subnetworks = ["192.168.0.0/16"]  # Replace with your allowed IP ranges
    }
  }
}

# Binary Authorization Policy
resource "google_binary_authorization_policy" "ma_policy" {
  project = var.project_id

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/fmp-api-proxy"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/llm-orchestrator"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/three-statement-modeler"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/dcf-valuation"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/cca-valuation"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/lbo-analysis"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/dd-agent"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/excel-exporter"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/reporting-dashboard"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/data-ingestion"
  }

  default_admission_rule {
    evaluation_mode  = "REQUIRE_ATTESTATION"
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"
  }
}

# Security Command Center Findings
resource "google_scc_source" "ma_security_source" {
  display_name = "M&A Analysis Security Source"
  description  = "Security findings for M&A Analysis Platform"
}

# Log sinks for security monitoring
resource "google_logging_project_sink" "security_logs" {
  name        = "ma-security-logs"
  destination = "storage.googleapis.com/${google_storage_bucket.security_logs.name}"
  filter      = "resource.type = cloud_run_revision AND (severity = ERROR OR severity = CRITICAL)"

  unique_writer_identity = true
}

resource "google_storage_bucket" "security_logs" {
  name          = "${var.project_id}-ma-security-logs"
  location      = var.region
  force_destroy = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

# IAM for security monitoring
resource "google_project_iam_member" "security_monitoring" {
  project = var.project_id
  role    = "roles/securitycenter.admin"
  member  = "serviceAccount:ma-security@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account" "ma_security" {
  account_id   = "ma-security"
  display_name = "M&A Security Service Account"
}
