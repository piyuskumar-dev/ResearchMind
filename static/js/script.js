// Global State Variables
let eventSource = null;
let finalReportMarkdown = "";

// Elements
const topicInput = document.getElementById("topic-input");
const runBtn = document.getElementById("run-btn");
const btnText = runBtn.querySelector(".btn-text");
const btnSpinner = runBtn.querySelector(".btn-spinner");
const consoleOutput = document.getElementById("console-output");

// Accordion Elements
const rawAccordions = document.getElementById("raw-accordions");
const rawSearchContent = document.getElementById("raw-search-content");
const rawScrapeContent = document.getElementById("raw-scrape-content");

// Result Cards
const reportCard = document.getElementById("report-card");
const reportContent = document.getElementById("report-content");
const downloadBtn = document.getElementById("download-report-btn");

const feedbackCard = document.getElementById("feedback-card");
const feedbackContent = document.getElementById("feedback-content");

// Set Topic helper for suggestions
function setTopic(value) {
    topicInput.value = value;
    topicInput.focus();
}

// Log messages inside terminal emulator
function writeLog(message, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const style = isError ? "color: #ff5f56; font-weight: 500;" : "";
    const logLine = `<span style="color: #605850;">[${timestamp}]</span> <span style="${style}">${message}</span>\n`;
    
    consoleOutput.innerHTML += logLine;
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// Reset UI state before starting pipeline
function resetUI() {
    // Clear logs
    consoleOutput.innerHTML = "";
    writeLog("Starting multi-agent research pipeline...");

    // Reset step cards to waiting state
    const steps = ["search", "scrape", "write", "critic"];
    steps.forEach(step => {
        const card = document.getElementById(`step-${step}`);
        const status = document.getElementById(`status-${step}`);
        
        card.className = "step-card";
        status.className = "step-status waiting";
        status.textContent = "WAITING";
    });

    // Hide previous results and raw dumps
    rawAccordions.classList.add("hidden");
    rawSearchContent.textContent = "";
    rawScrapeContent.textContent = "";
    
    reportCard.classList.add("hidden");
    reportContent.innerHTML = "";
    finalReportMarkdown = "";

    feedbackCard.classList.add("hidden");
    feedbackContent.innerHTML = "";
}

// Update state on a specific step card
function updateStepCard(stepName, statusState, details = "") {
    const card = document.getElementById(`step-${stepName}`);
    const status = document.getElementById(`status-${stepName}`);
    
    if (statusState === "running") {
        card.className = "step-card active";
        status.className = "step-status running";
        status.textContent = "● RUNNING";
        writeLog(`Agent: ${stepName.toUpperCase()} has started.`);
    } else if (statusState === "done") {
        card.className = "step-card done";
        status.className = "step-status done";
        status.textContent = "✓ DONE";
        writeLog(`Agent: ${stepName.toUpperCase()} completed successfully.`);
    }
}

// Initiate the SSE client connection
function startResearch() {
    const topic = topicInput.value.trim();
    if (!topic) {
        alert("Please enter a research topic first.");
        topicInput.focus();
        return;
    }

    resetUI();

    // Disable inputs and show spinners
    topicInput.disabled = true;
    runBtn.disabled = true;
    btnText.textContent = "Researching...";
    btnSpinner.classList.remove("hidden");

    // Connect to Server Sent Events endpoint
    const url = `/research/stream?topic=${encodeURIComponent(topic)}`;
    eventSource = new EventSource(url);

    eventSource.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);

            if (data.message) {
                writeLog(data.message);
            }

            // Route events depending on step
            switch (data.step) {
                case "search":
                    if (data.status === "running") {
                        updateStepCard("search", "running");
                    } else if (data.status === "done") {
                        updateStepCard("search", "done");
                        rawSearchContent.textContent = data.data;
                        rawAccordions.classList.remove("hidden");
                        document.getElementById("accordion-search").open = true;
                    }
                    break;

                case "scrape":
                    if (data.status === "running") {
                        updateStepCard("scrape", "running");
                    } else if (data.status === "done") {
                        updateStepCard("scrape", "done");
                        rawScrapeContent.textContent = data.data;
                        document.getElementById("accordion-scrape").open = true;
                    }
                    break;

                case "write":
                    if (data.status === "running") {
                        updateStepCard("write", "running");
                    } else if (data.status === "done") {
                        updateStepCard("write", "done");
                        
                        // Parse markdown natively using marked.js
                        reportContent.innerHTML = marked.parse(data.data);
                        reportCard.classList.remove("hidden");
                    }
                    break;

                case "critic":
                    if (data.status === "running") {
                        updateStepCard("critic", "running");
                    } else if (data.status === "done") {
                        updateStepCard("critic", "done");
                        
                        // Parse feedback markdown
                        feedbackContent.innerHTML = marked.parse(data.data);
                        feedbackCard.classList.remove("hidden");
                    }
                    break;

                case "complete":
                    writeLog("Pipeline complete! All reports generated.");
                    finalReportMarkdown = data.report;
                    cleanupConnection();
                    break;
            }
        } catch (err) {
            writeLog(`Error parsing stream event: ${err.message}`, true);
        }
    };

    eventSource.onerror = function (err) {
        writeLog("Connection to backend lost or encountered an error.", true);
        cleanupConnection();
    };
}

// Reset inputs and close connection safely
function cleanupConnection() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    // Enable inputs and restore button state
    topicInput.disabled = false;
    runBtn.disabled = false;
    btnText.textContent = "⚡ Run Research";
    btnSpinner.classList.add("hidden");
}

// Download Markdown Report helper
function downloadReport() {
    if (!finalReportMarkdown) return;
    
    const blob = new Blob([finalReportMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement("a");
    a.href = url;
    a.download = `research_report_${Math.floor(Date.now() / 1000)}.md`;
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Register Listeners
runBtn.addEventListener("click", startResearch);
topicInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        startResearch();
    }
});
downloadBtn.addEventListener("click", downloadReport);
