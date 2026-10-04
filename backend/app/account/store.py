"""Server-held login transactions and sessions; membership is loaded on every request."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from threading import RLock
from uuid import uuid4

from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import PostgresDatabase
from app.security.contracts import Principal, TrustedContext


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Session:
    context: TrustedContext
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class LoginFlow:
    browser_hash: str
    nonce: str
    code_verifier: str
    return_path: str


class PostgresAccountStore:
    def __init__(self, database=None):
        self.database = database or PostgresDatabase()

    def put_flow(self, state, browser, nonce, verifier, return_path):
        with self.database.connection() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM account.oidc_flows WHERE expires_at <= CURRENT_TIMESTAMP")
                conn.execute("""INSERT INTO account.oidc_flows
                    (state_hash,browser_hash,nonce,code_verifier,return_path,expires_at)
                    VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP + interval '5 minutes')""",
                    (fingerprint(state),fingerprint(browser),nonce,verifier,return_path))

    def consume_flow(self, state, browser):
        with self.database.connection() as conn:
            # Atomic consume: a replay cannot exchange a second code.
            row = conn.execute("""DELETE FROM account.oidc_flows
                WHERE state_hash=%s AND browser_hash=%s AND expires_at > CURRENT_TIMESTAMP
                RETURNING browser_hash,nonce,code_verifier,return_path""",
                (fingerprint(state),fingerprint(browser))).fetchone()
        return LoginFlow(*row) if row else None

    def bind_identity(self, issuer, subject, display_name):
        with self.database.connection() as conn:
            # Persist identity only. Creating a mapping never creates a tenant membership.
            row = conn.execute("""INSERT INTO account.principals
                (principal_id,oidc_issuer,oidc_subject,display_name) VALUES (%s,%s,%s,%s)
                ON CONFLICT (oidc_issuer,oidc_subject) DO UPDATE SET display_name=EXCLUDED.display_name
                RETURNING principal_id,enabled""",("usr_"+uuid4().hex,issuer,subject,display_name)).fetchone()
            if not row[1]:
                raise PermissionError("Principal is disabled")
            memberships = conn.execute("""SELECT tenant_id,roles,allowed_scopes FROM account.memberships
                WHERE principal_id=%s AND enabled ORDER BY tenant_id""",(row[0],)).fetchall()
        if len(memberships) != 1:
            raise PermissionError("A single explicit active tenant membership is required")
        tenant,roles,scopes = memberships[0]
        principal = Principal(tenant_id=tenant,principal_id=row[0],issuer=issuer,subject=subject,display_name=display_name,authentication="oidc")
        access = AccessContext(user_id=row[0],tenant_id=tenant,roles=tuple(roles),allowed_scopes=tuple(scopes))
        return TrustedContext(principal=principal,access=access,policy_version="server-membership-v1")

    def create_session(self, context, lifetime):
        token,csrf = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(seconds=lifetime)
        with self.database.connection() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM account.sessions WHERE expires_at <= CURRENT_TIMESTAMP")
                conn.execute("""INSERT INTO account.sessions (session_hash,principal_id,tenant_id,csrf_token,expires_at)
                    VALUES (%s,%s,%s,%s,%s)""",(fingerprint(token),context.principal.principal_id,context.access.tenant_id,csrf,expiry))
        return token,Session(context,csrf,expiry)

    def load_session(self, token):
        with self.database.connection() as conn:
            row = conn.execute("""SELECT p.principal_id,p.oidc_issuer,p.oidc_subject,p.display_name,
                m.tenant_id,m.roles,m.allowed_scopes,s.csrf_token,s.expires_at
                FROM account.sessions s JOIN account.principals p ON p.principal_id=s.principal_id
                JOIN account.memberships m ON m.principal_id=s.principal_id AND m.tenant_id=s.tenant_id
                WHERE s.session_hash=%s AND s.expires_at > CURRENT_TIMESTAMP AND p.enabled AND m.enabled""",
                (fingerprint(token),)).fetchone()
        if not row:
            return None
        principal = Principal(tenant_id=row[4],principal_id=row[0],issuer=row[1],subject=row[2],display_name=row[3],authentication="oidc")
        access = AccessContext(user_id=row[0],tenant_id=row[4],roles=tuple(row[5]),allowed_scopes=tuple(row[6]))
        expiry = datetime.fromisoformat(row[8].replace("Z","+00:00")) if isinstance(row[8],str) else row[8]
        return Session(TrustedContext(principal=principal,access=access,policy_version="server-membership-v1"),row[7],expiry)

    def revoke_session(self, token):
        with self.database.connection() as conn:
            conn.execute("DELETE FROM account.sessions WHERE session_hash=%s",(fingerprint(token),))


class DemoSessionStore:
    """Only for explicitly selected local demo; never used by OIDC/production."""
    def __init__(self):
        self.sessions = {}
        self.lock = RLock()

    def create_session(self, context, lifetime):
        token = secrets.token_urlsafe(32)
        session = Session(context,secrets.token_urlsafe(32),datetime.now(timezone.utc)+timedelta(seconds=lifetime))
        with self.lock:
            self.sessions[fingerprint(token)] = session
        return token,session

    def load_session(self, token):
        with self.lock:
            session = self.sessions.get(fingerprint(token))
            if session and session.expires_at > datetime.now(timezone.utc):
                return session
            self.sessions.pop(fingerprint(token),None)
        return None

    def revoke_session(self, token):
        with self.lock:
            self.sessions.pop(fingerprint(token),None)


demo_sessions = DemoSessionStore()
