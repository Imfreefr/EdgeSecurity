"""Pair sheets for actual visual comparison; no automatic exclusion."""
import json
from prepare_cctv_v2 import ROOT, AUDIT, sheet

def main():
    originals=json.loads((ROOT/'review/originals.json').read_text(encoding='utf-8'))
    audit=json.loads((AUDIT/'audit.json').read_text(encoding='utf-8'))
    for kind,pairs in [('near',audit['near_duplicate_candidate_pairs']),
                       ('exact',[{'a':x[0],'b':x[1]} for x in audit['exact_duplicate_groups']])]:
        for start in range(0,len(pairs),12):
            items=[]
            for number,pair in enumerate(pairs[start:start+12],start):
                for side in ('a','b'):
                    item=originals[pair[side]]
                    items.append({**item,'id':f'{kind}-{number:03d} {side}: {item["index"]:03d}'})
            sheet(items,ROOT/'review/sheets'/f'{kind}-pairs-{start//12+1:02d}.jpg')
    print('Pair sheets generated')

if __name__=='__main__':main()
