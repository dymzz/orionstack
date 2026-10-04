# Deployment reference only. Replace endpoints/paths through your deployment system.
# No real secrets or root tokens belong in the repository.
vault {
  address = "https://openbao.example.internal:8200"
}
auto_auth {
  method {
    type = "approle"
    config {
      role_id_file_path   = "/run/secrets/openbao-role-id"
      secret_id_file_path = "/run/secrets/openbao-secret-id"
    }
  }
}
template_config {
  exit_on_retry_failure = true
}
env_template "ORIONSTACK_DATABASE_URL" {
  contents = "{{ with secret \"secret/data/orionstack/core\" }}{{ .Data.data.database_url }}{{ end }}"
  error_on_missing_key = true
}
env_template "DEEPSEEK_API_KEY" {
  contents = "{{ with secret \"secret/data/orionstack/core\" }}{{ .Data.data.deepseek_api_key }}{{ end }}"
  error_on_missing_key = true
}
env_template "TYPESAFE_API_KEY" {
  contents = "{{ with secret \"secret/data/orionstack/core\" }}{{ .Data.data.typesafe_api_key }}{{ end }}"
  error_on_missing_key = true
}
env_template "ORIONSTACK_OIDC_CLIENT_SECRET" {
  contents = "{{ with secret \"secret/data/orionstack/account\" }}{{ .Data.data.oidc_client_secret }}{{ end }}"
  error_on_missing_key = true
}
exec {
  command = ["python", "scripts/start-backend.py", "--app-mode", "prod", "--host", "0.0.0.0", "--port", "8000"]
  restart_on_secret_changes = "always"
  restart_stop_signal = "SIGTERM"
}
