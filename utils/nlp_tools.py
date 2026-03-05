import re
import numpy as np
from fuzzywuzzy import fuzz
from sentence_transformers import SentenceTransformer

#  High-accuracy model
model = SentenceTransformer('paraphrase-mpnet-base-v2')

#  Normalize question (fix case, punctuation, repeated words)
def normalize(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)                  # remove punctuation
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)    # remove repeated words (e.g., "improve improve" -> "improve")
    text = re.sub(r'\s+', ' ', text).strip()             # clean up spacing
    return text

#  Generate embedding from normalized text
def get_sentence_embedding(text: str):
    normalized = normalize(text)
    return model.encode(normalized).tolist()

#  Cosine similarity
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

#  Hybrid similarity: cosine + fuzzy
def hybrid_similarity(text1, text2, vec1, vec2, weight_cosine=0.6):
    cos_sim = cosine_similarity(vec1, vec2)
    fuzzy_sim = fuzz.token_sort_ratio(text1, text2) / 100.0
    return weight_cosine * cos_sim + (1 - weight_cosine) * fuzzy_sim