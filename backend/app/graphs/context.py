"""Trim effective input only; neither business transcript nor checkpoints are deleted."""
from langchain_core.messages import trim_messages


def model_history(messages,allowed_turn_ids,current_id):
    filtered=[m for m in messages if m.additional_kwargs.get('turn_id') in allowed_turn_ids
              and m.additional_kwargs.get('turn_id')!=current_id and m.type in ('human','ai')]
    trimmed=trim_messages(filtered,max_tokens=3000,token_counter='approximate',strategy='last',
        start_on='human',allow_partial=False)
    history=[{'role':'user' if m.type=='human' else 'assistant','content':str(m.content)[:4000]} for m in trimmed][-10:]
    while sum(len(m['content']) for m in history)>12000:history=history[2:]
    return history
