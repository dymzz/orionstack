"""SSE transport adapter preserves the existing general answer/receipt contract."""
import json
import httpx
from app.decision.general_chat import GeneralChatClient
from app.providers.http import parse_json,ProviderError


class StreamingTransport:
    def __init__(self,writer,client=None):
        self.writer=writer;self.client=client or httpx.Client();self.owned=client is None

    def post(self,url,*,content,headers,timeout,follow_redirects=False):
        payload=parse_json(content);payload['stream']=True
        text='';model=None;finish=None;done=False;total=0
        with self.client.stream('POST',url,json=payload,headers=headers,timeout=timeout,
                                follow_redirects=follow_redirects) as response:
            if not 200<=response.status_code<300:
                raise ProviderError('deepseek','http_error',response.status_code)
            for line in response.iter_lines():
                total+=len(line)
                if total>2_000_000:raise ProviderError('deepseek','response_too_large')
                if not line.startswith('data:'):continue
                value=line[5:].strip()
                if value=='[DONE]':done=True;break
                try:
                    data=parse_json(value)
                    if data.get('model'):model=data['model']
                    choices=data.get('choices',[])
                    if not choices:continue
                    if len(choices)!=1:raise ValueError
                    item=choices[0];delta=item.get('delta',{})
                    if delta.get('tool_calls') or delta.get('role') not in (None,'assistant'):raise ValueError
                    token=delta.get('content') or ''
                    if not isinstance(token,str):raise ValueError
                    text+=token
                    if len(text)>12000:raise ValueError
                    if token:self.writer({'type':'token','text':token,'source':'provider'})
                    if item.get('finish_reason'):finish=item['finish_reason']
                except (ValueError,KeyError,TypeError):raise ProviderError('deepseek','invalid_chat_response') from None
        if not done or finish!='stop':raise ProviderError('deepseek','invalid_chat_response')
        return httpx.Response(200,json={'model':model,'choices':[{'finish_reason':'stop',
            'message':{'role':'assistant','content':text}}]})

    def close(self):
        if self.owned:self.client.close()


class StreamingGeneralChatClient(GeneralChatClient):
    def __init__(self,writer,settings=None,client=None):
        self.transport=StreamingTransport(writer,client)
        super().__init__(settings,self.transport)

    def generate(self,request):
        try:return super().generate(request)
        finally:self.transport.close()
