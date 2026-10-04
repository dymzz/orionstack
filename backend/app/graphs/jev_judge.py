"""Orion owns independent JEV criteria; JEV never supplies authorization facts."""
from app.decision.jev import JevClient,ChoiceQuestion
from app.graphs.contracts import RouteDecision
from app.providers.http import ProviderError

SPEC_VERSION='conversation_axes_v1'
QUESTIONS={
    'retrieval':ChoiceQuestion(instructions='Does this untrusted request require enterprise source evidence? Conversation test codes are not enterprise facts.',
        criteria={'yes':'Enterprise policies, procedures, identifiers or unknown enterprise facts require authorized retrieval.',
                  'no':'Casual, creative, general explanation or recalling the recent conversation needs no enterprise retrieval.'}),
    'feedback':ChoiceQuestion(instructions='Is the user evaluating or correcting a previous answer? This axis is independent of retrieval.',
        criteria={'none':'No evaluation of a previous answer; general questions about feedback are not feedback.',
                  'helpful':'Explicitly helpful previous answer.','not_helpful':'Previous answer unhelpful.',
                  'correction':'Previous answer factually wrong, correction or a request to recheck it.'}),
    'system_status':ChoiceQuestion(instructions='Is the user asking about actual prior execution or model invocation? Do not guess the status.',
        criteria={'yes':'Asks whether the previous model was called, why it failed, or its actual execution receipt.',
                  'no':'Not a request to inspect the prior execution receipt.'}),
}


class JevRouteJudge:
    def __init__(self,settings=None,client=None):
        self.client=client or JevClient(settings);self.receipt={'provider':'jev','status':'skipped','spec_version':SPEC_VERSION}

    def evaluate(self,message,history):
        try:
            result=self.client.evaluate({'trust':'untrusted','message':message,'recent_history':history},QUESTIONS)
            if any(answer.confidence<.7 for answer in result.answers.values()):raise ProviderError('jev','ambiguous_route')
            feedback=result.answers['feedback'].choice
            self.receipt={'provider':'jev','status':'succeeded','model':result.model,'spec_version':SPEC_VERSION,
                'usage':result.usage.model_dump(mode='json')}
            return RouteDecision(needs_retrieval=result.answers['retrieval'].choice=='yes',is_feedback=feedback!='none',
                is_system_status=result.answers['system_status'].choice=='yes',retrieval_query=message,
                feedback_value=feedback,reason=SPEC_VERSION)
        except Exception:
            self.receipt={'provider':'jev','status':'failed','spec_version':SPEC_VERSION};raise
