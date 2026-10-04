// Server-owned attributes only. An OIDC claim or user JSON cannot grant a role.
permit (principal, action == Action::"AttachFile", resource)
when { principal.tenant == resource.tenant && principal.roles.contains("admin") };

permit (principal, action == Action::"ReadAsset", resource)
when { principal.tenant == resource.tenant &&
       (principal.roles.contains("admin") || principal.id == resource.owner) };

permit (principal, action == Action::"FinalizeAsset", resource)
when { principal.tenant == resource.tenant &&
       (principal.roles.contains("admin") || principal.id == resource.owner) };

permit (principal, action in [Action::"ListBackups", Action::"DownloadBackup"], resource)
when { principal.tenant == resource.tenant && principal.backup_operator };

permit (principal, action == Action::"SystemDiagnostics", resource)
when { principal.tenant == resource.tenant && principal.roles.contains("admin") };

// The initial QA audit boundary is owner-only, including administrators.
permit (principal, action in [Action::"ReadRunAudit", Action::"SubmitFeedback", Action::"ListRunAudit"], resource)
when { principal.tenant == resource.tenant && principal.id == resource.owner };

// Conversations are owned by the authenticated principal, including admins.
permit (principal, action in [Action::"CreateConversation", Action::"UseConversation", Action::"ListConversation"], resource)
when { principal.tenant == resource.tenant && principal.id == resource.owner };
