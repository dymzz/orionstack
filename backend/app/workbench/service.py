from uuid import uuid4
from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.config.runtime_versions import chat_runtime_versions
from app.decision.general_chat import GeneralChatClient
from app.decision.model_call import observed_call
from app.knowledge.postgres import PostgresDatabase, DatabaseUnavailable
from app.providers.http import ProviderError
from app.workbench.contracts import GeneralChatResponse, RunFeedback
from app.workbench.repository import WorkbenchRunRepository


class GeneralChatService:
    def __init__(self, database=None, client=None, settings=None):
        self.settings=settings or CoreSettings()
        self.database=database or PostgresDatabase(self.settings)
        self.client=client or GeneralChatClient(self.settings)

    def chat(self, request, access):
        request_id=str(uuid4())
        versions=chat_runtime_versions(self.settings)
        try:
            answer, model=self.client.generate(request)
            feedback=RunFeedback(request_id=request_id,mode='general_chat',outcome='answered',reason='general_response',
                                 model_call=observed_call(self.client),runtime_versions=versions)
            result=GeneralChatResponse(tenant_id=access.tenant_id,request_id=request_id,answer=answer,model=model,
                                       execution_feedback=feedback)
        except (ProviderError,CoreConfigurationError) as error:
            feedback=RunFeedback(request_id=request_id,mode='general_chat',outcome='failed',
                reason='configuration_missing' if isinstance(error,CoreConfigurationError) else 'provider_failed',
                model_call=observed_call(self.client),runtime_versions=versions)
            self._save_or_raise(request,access,{'status':'failed','execution_feedback':feedback.model_dump(mode='json')},feedback)
            error.request_id=request_id
            error.execution_feedback=feedback
            raise
        self._save_or_raise(request,access,result.model_dump(mode='json'),feedback)
        return result

    def _save_or_raise(self,request,access,response,feedback):
        try:
            with self.database.connection() as connection:
                with connection.transaction():
                    WorkbenchRunRepository.save(connection,access,request.model_dump(mode='json'),response)
        except (DatabaseUnavailable,CoreConfigurationError) as error:
            error.request_id=feedback.request_id
            error.execution_feedback=feedback.model_copy(update={'outcome':'failed','reason':'audit_unavailable','audit_status':'unavailable'})
            raise
