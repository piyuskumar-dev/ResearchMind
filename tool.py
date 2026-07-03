
from langchain.tools import tool
import os
import requests
from tavily import TavilyClient
from dotenv import load_dotenv
load_dotenv()
from bs4 import BeautifulSoup
from rich import print

@tool
def web_search(query: str) -> str:
    """
    Search the web for a query and return the results in the form of a URL, title , content.
    """
    tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    response = tavily_client.search(query, max_results=3)

    output = []
    for result in response['results']:
        url = result['url']
        title = result['title']
        content = result['content']
        output.append(f"Title: {title}\nURL: {url}\nContent: {content}\n")

    return "\n".join(output)

@tool
def scrape_website(url: str) -> str:
    """
    Scrape the content of a website and return the cleaned text.
    """
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'})
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'footer', 'header', 'nav', 'aside']):
            tag.decompose()
        return soup.get_text(separator=' ', strip=True)[:2500]
    except Exception as e:
        print(f"Error occurred while scraping {url}: {e}")
