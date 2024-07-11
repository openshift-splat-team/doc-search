FROM  pytorch/pytorch:2.3.1-cuda12.1-cudnn8-devel
RUN apt-get update
RUN apt-get install -y libgbm-dev
RUN pip install -U sentence-transformers rank_bm25 langchain_community nest_asyncio playwright
RUN playwright install-deps     
RUN playwright install
WORKDIR /usr/app/src
RUN mkdir doc_html
COPY init.py .
RUN python init.py
COPY main.py .