import json, collections
docs = [json.loads(l) for l in open('Data/enriched_docs.jsonl', encoding='utf-8')]
t = len(docs)
print(f"Summary coverage: {sum(1 for d in docs if d.get('summary'))/t*100:.2f}%")
print(f"QA coverage: {sum(1 for d in docs if len(d.get('qa_pairs', []))>0)/t*100:.2f}%")
print('\nCategory dist:')
for k,v in collections.Counter(d.get('category') for d in docs).items(): print(f'  {k}: {v}')
print('\nDocument type dist:')
for k,v in collections.Counter(d.get('document_type') for d in docs).items(): print(f'  {k}: {v}')
