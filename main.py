import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from sentence_transformers import SentenceTransformer, CrossEncoder, util
import gzip
import os
import torch
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction import _stop_words
import string
from tqdm.autonotebook import tqdm
import numpy as np

class QueryHandler(SimpleHTTPRequestHandler):
    def do_POST(self):        
        length = int(self.headers['Content-Length'])
        messagecontent = self.rfile.read(length)

        response = "unable to find a match"
        _, url = search(query = str(messagecontent, "utf-8"))
        if url != None:
            response = url
            self.send_response(200)
        else:
            response = "unable to find a match"            
            self.send_response(403)
        print(url)
        self.end_headers()        
        self.wfile.write(response.encode('utf-8'))

def run(server_class=HTTPServer, handler_class=QueryHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd server on port {port}...')
    httpd.serve_forever()

# We lower case our text and remove stop-words from indexing
def bm25_tokenizer(text):
    tokenized_doc = []
    for token in text.lower().split():
        token = token.strip(string.punctuation)

        if len(token) > 0 and token not in _stop_words.ENGLISH_STOP_WORDS:
            tokenized_doc.append(token)
    return tokenized_doc

def search(query):
    print("Input question:", query)

    ##### BM25 search (lexical search) #####
    bm25_scores = bm25.get_scores(bm25_tokenizer(query))
    top_n = np.argpartition(bm25_scores, -5)[-5:]
    bm25_hits = [{'corpus_id': idx, 'score': bm25_scores[idx]} for idx in top_n]
    bm25_hits = sorted(bm25_hits, key=lambda x: x['score'], reverse=True)
    
    ##### Semantic Search #####
    # Encode the query using the bi-encoder and find potentially relevant passages
    question_embedding = bi_encoder.encode(query, convert_to_tensor=True)
    #question_embedding = question_embedding.cpu()#.cuda()
    hits = util.semantic_search(question_embedding, corpus_embeddings, top_k=top_k)
    hits = hits[0]  # Get the hits for the first query

    ##### Re-Ranking #####
    # Now, score all retrieved passages with the cross_encoder
    cross_inp = [[query, passages[hit['corpus_id']]] for hit in hits]
    cross_scores = cross_encoder.predict(cross_inp)

    # Sort results by the cross-encoder scores
    for idx in range(len(cross_scores)):
        hits[idx]['cross-score'] = cross_scores[idx]

    hits = sorted(hits, key=lambda x: x['score'], reverse=True)
    hits = sorted(hits, key=lambda x: x['cross-score'], reverse=True)

    if len(hits) < 1:
        return None, None

    hit = hits[0]
    if hit['cross-score'] < 1:
        return None, None
    
    return passages[hit['corpus_id']].replace("\n", " "), file_map["passage_" + str(hit['corpus_id'])]

file_map = {}
with open('./doc_html/file_map_with_hashes.json', 'r', encoding='utf-8') as file:
    file_map = json.load(file)

passages = []

with open('./doc_html/passages.json', 'r', encoding='utf-8') as file:
    passages = json.load(file)

if not torch.cuda.is_available():
    print("Warning: No GPU found. Please add GPU to your notebook")

#We use the Bi-Encoder to encode all passages, so that we can use it with semantic search
bi_encoder = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')
bi_encoder.max_seq_length = 256     #Truncate long passages to 256 tokens
top_k = 8                          #Number of passages we want to retrieve with the bi-encoder

#The bi-encoder will retrieve 100 documents. We use a cross-encoder, to re-rank the results list to improve the quality
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

print("Passages:", len(passages))

corpus_embeddings = bi_encoder.encode(passages, convert_to_tensor=True, show_progress_bar=True)

tokenized_corpus = []
for passage in tqdm(passages):
    tokenized_corpus.append(bm25_tokenizer(passage))

bm25 = BM25Okapi(tokenized_corpus)

# question = "What version of ESXi do I need to install OpenShift?"
# answer = search(query = question)
#print(answer)

run()