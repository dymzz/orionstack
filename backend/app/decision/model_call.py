"""Server observations of provider calls; never inferred from model prose."""
from typing import Literal
from pydantic import Field, StrictBool, model_validator
from app.config.core_settings import CoreConfigurationError
from app.knowledge.contracts import CoreContract
from app.providers.http import ProviderError


class ModelCallReceipt(CoreContract):
    provider: Literal['deepseek'] = 'deepseek'
    status: Literal['skipped', 'succeeded', 'failed', 'unknown']
    attempted: StrictBool | None
    model: str | None = Field(default=None, max_length=128)
    reason: Literal['not_requested', 'no_raw_candidates', 'processing_filtered_all', 'sources_unavailable',
                    'retrieval_failed', 'configuration_missing', 'response_received', 'provider_failed',
                    'unverified_model_output', 'adapter_unobserved']
    error_code: str | None = Field(default=None, max_length=128, pattern=r'^[a-z0-9_:-]+$')

    @model_validator(mode='after')
    def consistent(self):
        if ((self.status == 'skipped' and self.attempted is not False)
                or (self.status == 'succeeded' and (self.attempted is not True or not self.model))
                or (self.status == 'unknown' and self.attempted is not None)):
            raise ValueError('Model call status must match server observations')
        return self


def skipped_call(reason='not_requested'):
    return ModelCallReceipt(status='skipped', attempted=False, reason=reason)


class ModelCallTracker:
    def __init__(self):
        self.attempted = False
        self.receipt = skipped_call()

    def on_attempt(self):
        self.attempted = True

    def succeeded(self, model):
        if self.attempted:
            self.receipt = ModelCallReceipt(status='succeeded', attempted=True, model=model, reason='response_received')
        else:
            self.receipt = ModelCallReceipt(status='unknown', attempted=None, model=model, reason='adapter_unobserved')

    def failed(self, error):
        configuration = isinstance(error, CoreConfigurationError)
        code = getattr(error, 'code', None)
        allowed = {'invalid_request', 'input_too_large', 'http_error', 'response_too_large', 'invalid_json',
                   'invalid_response', 'timeout', 'transport_error', 'unverified_excerpt_response', 'invalid_chat_response'}
        self.receipt = ModelCallReceipt(status='failed', attempted=self.attempted,
            reason='configuration_missing' if configuration else
                   ('unverified_model_output' if code in {'unverified_excerpt_response', 'invalid_chat_response'} else 'provider_failed'),
            error_code='configuration_error' if configuration else code if code in allowed else 'unexpected_provider_failure')


def observed_call(client):
    # Only a server adapter carrying this tracker is an observation source.
    tracker = getattr(client, '_call_tracker', None)
    return tracker.receipt if isinstance(tracker, ModelCallTracker) else ModelCallReceipt(
        status='unknown', attempted=None, reason='adapter_unobserved')
