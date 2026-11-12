"""Deterministic bounded lexical ranking over supplied versioned text only."""
import math
import re
from collections import Counter

def tokens(text):
    words=re.findall(r'[a-z0-9]+|[\u3400-\u9fff]',text.casefold())
    han=re.findall(r'[\u3400-\u9fff]+',text)
    return words+[s[i:i+2] for s in han for i in range(len(s)-1)]

def chunks(text, size=900, overlap=120):
    return [(start,min(start+size,len(text))) for start in range(0,len(text),size-overlap)]

def search(documents,query,limit):
    q=set(tokens(query));parts=[]
    for d in documents:
        for start,end in chunks(d['text']):
            count=Counter(tokens(d['text'][start:end]));parts.append((d,start,end,count,sum(count.values())))
    if not q or not parts:return []
    n=len(parts);avg=sum(p[4] for p in parts)/n or 1
    df={w:sum(w in p[3] for p in parts) for w in q}
    ranked=[]
    for d,start,end,count,length in parts:
        score=sum(math.log(1+(n-df[w]+.5)/(df[w]+.5))*count[w]*2.2/(count[w]+1.2*(.25+.75*length/avg)) for w in q if count[w])
        if score>0:
            ranked.append({'ref':d['ref'],'title':d['title'],'start':start,'end':end,
                           'quote':d['text'][start:end],'score':round(score,6),'content_scope':d['scope'],
                           'locator':next((p for p in d.get('pages',[]) if p['start']<=start<p['end']),None)})
    return sorted(ranked,key=lambda x:(-x['score'],x['ref']['asset_id'],x['start']))[:limit]
