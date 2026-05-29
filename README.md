# AI SDR (Sales Development Representative) 🤖

An advanced multi-agent system built with **LangGraph**, **LangChain**, and **Streamlit** that automates the process of researching companies, formulating sales strategies, and drafting highly personalized cold emails.

## 🌟 Features

- **Multi-Agent Architecture**: Utilizes LangGraph to orchestrate multiple specialized AI agents working together in a stateful workflow.
- **Automated Research**: Integrates with the **Tavily Search API** to gather real-time data, recent news, and product information about a target company.
- **Early Termination (Validation)**: If the target company does not exist or valid information cannot be found, the workflow efficiently terminates early to save API costs and time.
- **Strategic Analysis**: Analyzes the collected data to identify pain points and craft a compelling B2B value proposition.
- **Smart Copywriting**: Generates concise, personalized cold emails tailored to the specific prospect without using generic marketing clichés.
- **Iterative Quality Control (Spam Filter)**: Features an internal "Spam Checker" node that evaluates the generated email. If the email sounds too promotional or generic, the graph loops back, providing constructive feedback to the Copywriter agent until the email passes the filter (up to a 3-attempt limit).
- **Interactive UI**: A clean, real-time web interface built with **Streamlit** that streams the workflow's thought process, agent outputs, and final results.

## 🏗️ Architecture Workflow

The workflow is managed by a `StateGraph` that passes a typed state dictionary (`SDRState`) between the following nodes:

1. **Researcher Agent**: Takes a company name/URL, searches the web, and summarizes the company's core business and target audience. 
   - *Conditional Edge*: If no valid company information is found, the workflow ends immediately.
2. **Strategist Agent**: Reads the research summary and formulates a tailored sales approach and pain points.
3. **Copywriter Agent**: Drafts the cold email based on the strategy.
4. **Spam Checker Node**: Validates the email for "salesy" language. 
   - *Conditional Edge*: If flagged as spam, it routes back to the Copywriter with specific feedback for a rewrite. If it passes (or reaches the maximum number of attempts), the workflow terminates successfully.

## 🛠️ Tech Stack

- **Python 3.10+**
- **[LangGraph](https://python.langchain.com/)**: For stateful, multi-actor LLM orchestration.
- **[LangChain](https://www.langchain.com/)**: For LLM interactions, prompts, and tool integration.
- **[Streamlit](https://streamlit.io/)**: For the interactive web application front-end.
- **[OpenAI API](https://openai.com/)**: Core LLM engine (default: `gpt-5.4-mini`).
- **[Tavily API](https://tavily.com/)**: Optimized internet search for AI agents.

## 🚀 Setup and Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ai-sdr-langgraph.git
   cd ai-sdr-langgraph
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   OPENAI_MODEL_NAME=gpt-5.4-mini  # Optional: customize your preferred OpenAI model
   ```

5. **Run the Application**
   ```bash
   streamlit run app.py
   ```

## 💡 Usage

1. Open the Streamlit web interface in your browser (usually `http://localhost:8501`).
2. In the sidebar, enter the **Company Name** and **Website URL** of your target client.
3. Click **Launch Agents 🚀**.
4. Watch the agents execute their tasks in real-time. You can expand each node's output to see intermediate thoughts, the strategy formulated, and any spam-check feedback loops.
5. Review the final, ready-to-send personalized cold email!

---
*Developed as a portfolio project showcasing modern AI automation and multi-agent workflows.*