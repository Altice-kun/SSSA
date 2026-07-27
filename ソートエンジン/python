import math
import random

def calculate_sssa_score(query_str, doc):
    query_words = [w.strip().lower() for w in query_str.split() if w.strip()]
    if not query_words:
        return 0.0, 0.0, 0.0

    name_txt = doc['name'].lower()
    content_txt = doc['content'].lower()
    desc_txt = doc['description'].lower()

    all_text = f"{name_txt} {content_txt} {desc_txt}"
    matched_words = sum(1 for word in query_words if word in all_text)
    match_count_score = matched_words / len(query_words)

    total_tf = sum(all_text.count(word) for word in query_words)
    term_freq_score = min(1.0, math.log1p(total_tf) / 3.0)
    context_score = doc.get('context_score', 0.5)

    base_score = (match_count_score + term_freq_score + context_score) / 3.0

    fields = [name_txt, content_txt, desc_txt]
    hit_fields = sum(1 for f in fields if any(word in f for word in query_words))
    p_field = (hit_fields / len(fields)) * 100.0

    sssa_score = base_score * (p_field / 100.0)

    return round(sssa_score, 4), round(base_score, 4), round(p_field, 1)

def partition_into_10_buckets(active_items):
    buckets = [[] for _ in range(10)]
    for item in active_items:
        comp_score = item["score"] * 0.7 + item["base"] * 0.3
        b_idx = int((1.0 - min(1.0, max(0.0, comp_score))) * 10)
        if b_idx >= 10:
            b_idx = 9
        buckets[b_idx].append(item)

    partitioned = []
    for b in buckets:
        random.shuffle(b)
        partitioned.extend(b)
    return partitioned
