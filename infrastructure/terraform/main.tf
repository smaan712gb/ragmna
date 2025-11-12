terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "aiplatform.googleapis.com"
  ])

  service = each.key
  disable_on_destroy = false
}

# Cloud Storage buckets
resource "google_storage_bucket" "data_ingestion" {
  name          = "${var.project_id}-rag-ingestion-data"
  location      = var.region
  force_destroy = true

  versioning {
    enabled = true
  }
}

resource "google_storage_bucket" "financial_reports" {
  name          = "${var.project_id}-financial-reports"
  location      = var.region
  force_destroy = true

  versioning {
    enabled = true
  }
}

# Cloud SQL PostgreSQL database
resource "google_sql_database_instance" "main" {
  name             = "${var.project_id}-rag-db"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-f1-micro"

    disk_autoresize = true
    disk_size       = 10
    disk_type       = "PD_SSD"

    backup_configuration {
      enabled = true
      start_time = "02:00"
    }

    maintenance_window {
      day  = 7
      hour = 3
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "rag_database" {
  name     = "rag_ingestion_db"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "db_user" {
  name     = "rag_user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}

# Pub/Sub topics
resource "google_pubsub_topic" "data_processing" {
  name = "rag-ingestion-data-processing-topic"
}

# Secret Manager secrets
resource "google_secret_manager_secret" "fmp_api_key" {
  secret_id = "fmp-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "service_api_key" {
  secret_id = "service-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"
  replication {
    automatic = true
  }
}

# Cloud Run services
resource "google_cloud_run_service" "fmp_proxy" {
  name     = "fmp-api-proxy"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/fmp-api-proxy:latest"

        env {
          name  = "FMP_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.fmp_api_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "llm_orchestrator" {
  name     = "llm-orchestrator"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/llm-orchestrator:latest"

        env {
          name  = "FMP_PROXY_URL"
          value = google_cloud_run_service.fmp_proxy.status[0].url
        }

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name  = "VERTEX_PROJECT"
          value = var.project_id
        }

        env {
          name  = "VERTEX_LOCATION"
          value = var.region
        }

        resources {
          limits = {
            cpu    = "2000m"
            memory = "2Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "three_statement_modeler" {
  name     = "three-statement-modeler"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/three-statement-modeler:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "dcf_valuation" {
  name     = "dcf-valuation"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/dcf-valuation:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "cca_valuation" {
  name     = "cca-valuation"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/cca-valuation:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "lbo_analysis" {
  name     = "lbo-analysis"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/lbo-analysis:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "mergers_model" {
  name     = "mergers-model"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/mergers-model:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "dd_agent" {
  name     = "dd-agent"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/dd-agent:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name  = "VERTEX_PROJECT"
          value = var.project_id
        }

        env {
          name  = "VERTEX_LOCATION"
          value = var.region
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "excel_exporter" {
  name     = "excel-exporter"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/excel-exporter:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "reporting_dashboard" {
  name     = "reporting-dashboard"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/reporting-dashboard:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_service" "data_ingestion" {
  name     = "data-ingestion"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/data-ingestion:latest"

        env {
          name  = "SERVICE_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.service_api_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "VERTEX_PROJECT"
          value = var.project_id
        }

        env {
          name  = "VERTEX_LOCATION"
          value = var.region
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

# IAM bindings for Cloud Run
resource "google_cloud_run_service_iam_member" "fmp_proxy_invoker" {
  service  = google_cloud_run_service.fmp_proxy.name
  location = google_cloud_run_service.fmp_proxy.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "llm_orchestrator_invoker" {
  service  = google_cloud_run_service.llm_orchestrator.name
  location = google_cloud_run_service.llm_orchestrator.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "three_statement_modeler_invoker" {
  service  = google_cloud_run_service.three_statement_modeler.name
  location = google_cloud_run_service.three_statement_modeler.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "dcf_valuation_invoker" {
  service  = google_cloud_run_service.dcf_valuation.name
  location = google_cloud_run_service.dcf_valuation.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "cca_valuation_invoker" {
  service  = google_cloud_run_service.cca_valuation.name
  location = google_cloud_run_service.cca_valuation.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "lbo_analysis_invoker" {
  service  = google_cloud_run_service.lbo_analysis.name
  location = google_cloud_run_service.lbo_analysis.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "mergers_model_invoker" {
  service  = google_cloud_run_service.mergers_model.name
  location = google_cloud_run_service.mergers_model.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "dd_agent_invoker" {
  service  = google_cloud_run_service.dd_agent.name
  location = google_cloud_run_service.dd_agent.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "excel_exporter_invoker" {
  service  = google_cloud_run_service.excel_exporter.name
  location = google_cloud_run_service.excel_exporter.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "reporting_dashboard_invoker" {
  service  = google_cloud_run_service.reporting_dashboard.name
  location = google_cloud_run_service.reporting_dashboard.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "data_ingestion_invoker" {
  service  = google_cloud_run_service.data_ingestion.name
  location = google_cloud_run_service.data_ingestion.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Vertex AI RAG Engine configuration
resource "google_vertex_ai_index" "rag_vector_index" {
  display_name = "rag-vector-index"
  region       = var.region

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.data_ingestion.name}/vector-index/"
    config {
      dimensions = 768
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 10
        }
      }
    }
  }
}

# Monitoring and alerting
resource "google_monitoring_alert_policy" "service_down" {
  display_name = "M&A Analysis Service Down"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run service is down"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\""
      duration        = "300s"
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
