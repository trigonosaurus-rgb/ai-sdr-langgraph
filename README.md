# AI SDR (Sales Development Representative) 🤖

An advanced multi-agent system built with **LangGraph**, **LangChain**, and **Streamlit** that automates the process of researching companies, formulating sales strategies, and drafting highly personalized cold emails.

## 🌟 Features

- **Multi-Agent Architecture**: Utilizes LangGraph to orchestrate multiple specialized AI agents working together in a stateful workflow.
- **Automated Research**: Integrates with the **Tavily Search API** to gather real-time data, recent news, and product information about a target company.
- **Strategic Analysis**: Analyzes the collected data to identify pain points and craft a compelling B2B value proposition.
- **Smart Copywriting**: Generates concise, personalized cold emails without generic clichés.
- **Iterative Quality Control (Spam Filter)**: Features an internal "Spam Checker" node that evaluates the generated email. If the email sounds too promotional or generic, the graph loops back, providing constructive feedback to the Copywriter agent until the email passes the filter (or reaches a retry limit).
- **Interactive UI**: A clean, real-time web interface built with **Streamlit** that streams the workflow's thought process and outputs.

## 🏗️ Architecture

The workflow is managed by a `StateGraph` that passes a typed state dictionary (`SDRState`) between the following nodes:

1. **Researcher Agent**: Takes a company name/URL, searches the web, and summarizes the company's core business and target audience.
2. **Strategist Agent**: Reads the research summary and formulates a tailored sales approach and pain points.
3. **Copywriter Agent**: Drafts the cold email based on the strategy.
4. **Spam Checker Node**: Validates the email. 
   - *Conditional Edge*: If flagged as spam, it routes back to the Copywriter with specific feedback. If it passes, the workflow terminates.

## 🛠️ Tech Stack

- **Python 3.10+**
- **[LangGraph](https://python.langchain.com/v0.1/docs/langgraph/)**: For stateful, multi-actor LLM orchestration.
- **[LangChain](https://www.langchain.com/)**: For LLM interactions and prompt templating.
- **[Streamlit](https://streamlit.io/)**: For the interactive web application.
- **[OpenAI API](https://openai.com/)**: Core LLM engine (default: `gpt-5.4-mini` / `gpt-4o-mini`).
- **[Tavily API](https://tavily.com/)**: Optimized internet search for AI agents.

## 🚀 Setup and Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ai-sdr-langgraph.git
   cd ai-sdr-langgraph
   ```

2. **Install dependencies**
   Create a virtual environment (optional but recommended) and install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Rename the provided `.env.example` file to `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   OPENAI_MODEL_NAME=gpt-4o-mini  # Or your preferred OpenAI model
   ```

4. **Run the Application**
   ```bash
   streamlit run app.py
   ```

## 💡 Usage

1. Open the Streamlit web interface in your browser (usually `http://localhost:8501`).
2. In the sidebar, enter the **Company Name** and **Website URL** of your target client.
3. Click **Launch Agents 🚀**.
4. Watch the agents execute their tasks in real-time, expanding the nodes to see the intermediate thoughts, strategy, and spam-check feedback.
5. Review the final, ready-to-send personalized cold email!

---
*Developed as a portfolio project showcasing modern AI automation and multi-agent workflows.*