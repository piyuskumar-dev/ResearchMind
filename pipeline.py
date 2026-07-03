from agents import create_search_agent, create_scrape_agent, chain, critic_chain

def extract_text_content(content) -> str:
    """
    Helper to extract text from LLM response blocks, filtering out thinking blocks if present.
    """
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if block.get("type") == "text")
    return str(content)

def research_pipeline(topic: str) -> dict:
    """
    Generate a research report on a given topic using web search and website scraping.
    """
    search_agent = create_search_agent()
    scrape_agent = create_scrape_agent()

    state = {}

    print(f"\n" + "="*50)
    print(f"Step-1 Searching the web for topic: {topic}\n Please wait...")
    # Step 1: Search the web for the topic
    search_results = search_agent.invoke({
        "messages":[("user", f"Search the web for recent , reliable and detailed information on the topic: {topic}.")]
    })

    # Try to find the tool response which contains the raw search results (with URLs)
    tool_message = next((msg for msg in search_results['messages'] if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage"), None)
    if tool_message:
        state['search_results'] = extract_text_content(tool_message.content)
    else:
        state['search_results'] = extract_text_content(search_results['messages'][-1].content)

    print(f"\n Search Results:\n{state['search_results']}\n")

    # Step 2: Scrape the content of the top URLs from the search results
    print("\n"+" ="*50)
    print("step 2 - Scrape agent is scraping top resources ...")
    print("="*50)

    reader_result = scrape_agent.invoke({
        "messages": [("user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    })

    state['scraped_content'] = extract_text_content(reader_result['messages'][-1].content)

    print("\nscraped content: \n", state['scraped_content'])

    # Step 3: Combine the research gathered
    print("\n"+" ="*50)
    print("step 3 - Writer is drafting the report ...")
    print("="*50)

    research_combined = (
        f"SEARCH RESULTS : \n {state['search_results']} \n\n"
        f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}"
    )

    state["report"] = chain.invoke({
        "topic" : topic,
        "research" : research_combined
    })

    print("\n Final Report\n",state['report'])

    # Step 4: Generate the research report
    #critic report 

    print("\n"+" ="*50)
    print("step 4 - critic is reviewing the report ")
    print("="*50)

    state["feedback"] = critic_chain.invoke({
        "report":state['report']
    })

    print("\n critic report \n", state['feedback'])

    return state



if __name__ == "__main__":
    topic = input("\n Enter a research topic : ")
    research_pipeline(topic)