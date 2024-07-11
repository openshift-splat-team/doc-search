from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from langchain_community.document_transformers import Html2TextTransformer
from langchain_community.vectorstores import FAISS
from pathlib import Path
import hashlib
from bs4 import BeautifulSoup
import re
import json
import requests
import nest_asyncio

nest_asyncio.apply()

def getPageContentWithLinks(url):
    urls = []    
    pdfs = []
    loader = AsyncChromiumLoader([url])
    html = loader.load()
    
    for doc in html:
        soup = BeautifulSoup(doc.page_content, 'html.parser')
        text = soup.get_text()
        links = soup.find_all('a')
        for link in links:
            href = link.get('href')

            if href == None: 
                continue
                
            if '/en/documentation/openshift_container_platform/4.16/html/' in href and "#" not in href and not href.endswith(".pdf"):
                urls.append(href)
                
            #if href == None or '/en/documentation/openshift_container_platform/4.16/html/installing/installing-on-vsphere#' not in href:
            
            if href and href.endswith(".pdf"):
                pdfs.append(href)
                
    return urls, pdfs

def getURLsToSplit():
    base_domain="https://docs.redhat.com"    
    linkList = []
    links, _ = getPageContentWithLinks("https://docs.redhat.com/en/documentation/openshift_container_platform/4.16/")
    for link in links:
        print("checking " + link)
        innerLinks, _ = getPageContentWithLinks("https://docs.redhat.com"+link)    
        for innerLink in innerLinks:
            if innerLink.endswith("index"):
                continue
            linkList.append(base_domain + innerLink)                  
    return linkList

def getSectionContent(element):
    paragraphs=element.find_all("p")
    text=""
    for paragraph in paragraphs:
        part = paragraph.get_text().strip()
        part = re.sub("\\\\t", "", part)
        part = re.sub("\\\\n", "\n", part)
        part = re.sub("\\xa0", " ", part)
        text += part + " "    
    return text

links = set(getURLsToSplit())

main_class = "docs-content-container"

limit = len(links)
idx=1
passages = []

file_map = {}

for link in links:
    print('\rprocessing link ' + str(idx) + " of " + str(limit) , end='\r')
    if "legal-notice" in link or link in "release-notes":
        continue
    response = requests.get(link)
    web_content = response.content
    file_name = "./doc_html/" + str(idx) + ".html"

    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(str(response.content))
        file_map[idx] = link
        idx += 1

passages = []
directory = Path('./doc_html/')

file_name = "./doc_html/file_map.json"
with open(file_name, 'w', encoding='utf-8') as file:
    json.dump(file_map, file)

passageIdx = 0

for file_path in directory.iterdir():
    if file_path.is_file() and file_path.suffix == ".html":
        web_content = Path(file_path).read_text()

        mapIdx = file_path.name.split(".")[0]
        docUrl = file_map[int(mapIdx)]        
        
        soup = BeautifulSoup(web_content, 'html.parser')
        
        main_element = soup.find(class_=main_class)
        section_list=(main_element.find_all("section", class_="section"))

        print(str(file_path) + ": " + str(len(section_list)), end="\r")        
        for section in section_list:
            m = hashlib.sha256()
            section_id = section.attrs["id"]            
            content = getSectionContent(section)
            m.update(bytes(content, "utf-8"))            
            sectionUrl = docUrl + "#" + section_id
            file_map[m.hexdigest()] = sectionUrl
            file_map["passage_" + str(passageIdx)] = sectionUrl
            passages.append(content)
            passageIdx += 1

with open('./doc_html/passages.json', 'w', encoding='utf-8') as file:
    json.dump(passages, file)

with open('./doc_html/file_map_with_hashes.json', 'w', encoding='utf-8') as file:
    json.dump(file_map, file)