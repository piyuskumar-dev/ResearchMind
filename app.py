import os
import json
import asyncio
import time
from typing import Annotated
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from agents import create_search_agent, create_scrape_agent, chain, critic_chain

# Initialize FastAPI app
app = FastAPI(title="ResearchMind AI API")

# Enable CORS for robust communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    topic: Annotated[str, Field(description="The topic you want to research")]

def extract_text_content(content) -> str:
    """
    Helper to extract text from LLM response blocks, filtering out thinking blocks if present.
    """
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if block.get("type") == "text")
    return str(content)

@app.post('/research')
async def research_pipeline_json(request: ResearchRequest) -> dict:
    """
    Standard HTTP POST endpoint that executes the entire pipeline synchronously 
    on the backend and returns the final combined results as JSON.
    """
    topic_str = request.topic
    search_agent = create_search_agent()
    scrape_agent = create_scrape_agent()
    
    # Run blocking operations inside loop executor
    loop = asyncio.get_running_loop()
    state = {}

    # Step 1: Search
    search_results = await loop.run_in_executor(None, lambda: search_agent.invoke({
        "messages": [("user", f"Search the web for recent, reliable and detailed information on the topic: {topic_str}.")]
    }))
    tool_message = next((msg for msg in search_results['messages'] if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage"), None)
    state['search_results'] = extract_text_content(tool_message.content) if tool_message else extract_text_content(search_results['messages'][-1].content)

    # Step 2: Scrape
    reader_result = await loop.run_in_executor(None, lambda: scrape_agent.invoke({
        "messages": [("user",
            f"Based on the following search results about '{topic_str}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    }))
    state['scraped_content'] = extract_text_content(reader_result['messages'][-1].content)

    # Step 3: Write
    research_combined = (
        f"SEARCH RESULTS : \n {state['search_results']} \n\n"
        f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}"
    )
    state["report"] = await loop.run_in_executor(None, lambda: chain.invoke({
        "topic": topic_str,
        "research": research_combined
    }))

    # Step 4: Critic
    state["feedback"] = await loop.run_in_executor(None, lambda: critic_chain.invoke({
        "report": state['report']
    }))

    return JSONResponse(status_code=200, content=state)


@app.get('/research/stream')
async def research_pipeline_stream(topic: str = Query(..., description="The topic to research")):
    """
    Server-Sent Events (SSE) streaming endpoint that executes the pipeline and streams 
    progress updates (Step 1 to Step 4 status, partial contents, and final completion) 
    in real time to the browser UI.
    """
    async def event_generator():
        loop = asyncio.get_running_loop()
        
        # Step 0: Start
        yield f"data: {json.dumps({'step': 'start', 'message': 'Initializing agents and components...'})}\n\n"
        await asyncio.sleep(0.5)

        # Step 1: Search
        yield f"data: {json.dumps({'step': 'search', 'status': 'running', 'message': f'Searching the web for \"{topic}\"...'})}\n\n"
        search_agent = create_search_agent()
        search_results = await loop.run_in_executor(None, lambda: search_agent.invoke({
            "messages": [("user", f"Search the web for recent, reliable and detailed information on the topic: {topic}.")]
        }))
        tool_message = next((msg for msg in search_results['messages'] if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage"), None)
        search_content = extract_text_content(tool_message.content) if tool_message else extract_text_content(search_results['messages'][-1].content)
        
        yield f"data: {json.dumps({'step': 'search', 'status': 'done', 'data': search_content})}\n\n"
        await asyncio.sleep(0.5)

        # Step 2: Scrape
        yield f"data: {json.dumps({'step': 'scrape', 'status': 'running', 'message': 'Scraping top resource content...'})}\n\n"
        scrape_agent = create_scrape_agent()
        reader_result = await loop.run_in_executor(None, lambda: scrape_agent.invoke({
            "messages": [("user",
                f"Based on the following search results about '{topic}', "
                f"pick the most relevant URL and scrape it for deeper content.\n\n"
                f"Search Results:\n{search_content[:800]}"
            )]
        }))
        scraped_content = extract_text_content(reader_result['messages'][-1].content)
        
        yield f"data: {json.dumps({'step': 'scrape', 'status': 'done', 'data': scraped_content})}\n\n"
        await asyncio.sleep(0.5)

        # Step 3: Write
        yield f"data: {json.dumps({'step': 'write', 'status': 'running', 'message': 'Writing detailed research report...'})}\n\n"
        research_combined = (
            f"SEARCH RESULTS : \n {search_content} \n\n"
            f"DETAILED SCRAPED CONTENT : \n {scraped_content}"
        )
        report = await loop.run_in_executor(None, lambda: chain.invoke({
            "topic": topic,
            "research": research_combined
        }))
        
        yield f"data: {json.dumps({'step': 'write', 'status': 'done', 'data': report})}\n\n"
        await asyncio.sleep(0.5)

        # Step 4: Critic
        yield f"data: {json.dumps({'step': 'critic', 'status': 'running', 'message': 'Submitting draft to critic chain...'})}\n\n"
        feedback = await loop.run_in_executor(None, lambda: critic_chain.invoke({
            "report": report
        }))
        
        yield f"data: {json.dumps({'step': 'critic', 'status': 'done', 'data': feedback})}\n\n"
        await asyncio.sleep(0.5)

        # Step 5: Complete
        yield f"data: {json.dumps({'step': 'complete', 'status': 'done', 'report': report, 'feedback': feedback})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount the static directory to serve frontend assets (js, css, images, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    """
    Serves the main frontend dashboard at the root URL path.
    """
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    # Start the FastAPI application on port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)