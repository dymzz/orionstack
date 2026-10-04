-- Identity/session boundary storage. No passwords, OAuth tokens or claim-derived grants.
CREATE SCHEMA IF NOT EXISTS account;
CREATE TABLE account.principals (
    principal_id text PRIMARY KEY,
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    display_name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (oidc_issuer, oidc_subject)
);
CREATE TABLE account.memberships (
    principal_id text NOT NULL REFERENCES account.principals(principal_id),
    tenant_id text NOT NULL,
    roles text[] NOT NULL CHECK (cardinality(roles) > 0),
    allowed_scopes text[] NOT NULL CHECK (cardinality(allowed_scopes) > 0),
    enabled boolean NOT NULL DEFAULT true,
    PRIMARY KEY (principal_id, tenant_id)
);
CREATE TABLE account.sessions (
    session_hash text PRIMARY KEY,
    principal_id text NOT NULL,
    tenant_id text NOT NULL,
    csrf_token text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamptz NOT NULL,
    FOREIGN KEY (principal_id, tenant_id) REFERENCES account.memberships(principal_id, tenant_id)
);
CREATE INDEX account_sessions_expiry ON account.sessions (expires_at);
CREATE TABLE account.oidc_flows (
    state_hash text PRIMARY KEY,
    browser_hash text NOT NULL,
    nonce text NOT NULL,
    code_verifier text NOT NULL,
    return_path text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX account_oidc_flows_expiry ON account.oidc_flows (expires_at);
