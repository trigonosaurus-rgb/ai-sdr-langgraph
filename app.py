import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env before importing other modules
load_dotenv()

from core.graph import app as sdr_graph

st.set_page_config(page_title="AI SDR Agent", page_icon="🤖", layout="wide")

st.title("🤖 AI SDR (Multi-Agent System with LangGraph)")
st.markdown("This tool automatically researches a company, formulates a sales strategy, and writes a cold email.")

# Sidebar for input data
with st.sidebar:
    st.header("Target Settings")
    company_name = st.text_input("Company Name", placeholder="e.g., OpenAI")
    company_url = st.text_input("Website URL", placeholder="e.g., https://openai.com")
    
    start_button = st.button("Launch Agents 🚀", type="primary", use_container_width=True)

# Main execution logic
if start_button:
    if not company_name or not company_url:
        st.error("Please enter the company name and website URL!")
    else:
        # Initialize the starting state
        initial_state = {
            "company_name": company_name,
            "company_url": company_url,
            "research_iterations": 0
        }
        
        st.subheader("Agents Workflow Progress:")
        
        # Start streaming graph events
        # stream() yields dictionaries with updates from each node
        try:
            final_email = ""
            for output in sdr_graph.stream(initial_state):
                # output looks like: {'researcher': {'company_info': '...'}}
                for node_name, state_update in output.items():
                    # Remember the email when the copywriter updates it
                    if "email_draft" in state_update:
                        final_email = state_update["email_draft"]
                        
                    with st.expander(f"✅ Node completed: {node_name.upper()}", expanded=True):
                        if node_name == "researcher":
                            st.write("**Collected Information:**")
                            st.info(state_update.get("company_info", ""))
                        
                        elif node_name == "strategist":
                            st.write("**Sales Strategy:**")
                            st.success(state_update.get("strategy", ""))
                            
                        elif node_name == "copywriter":
                            st.write("**Email Draft:**")
                            st.code(state_update.get("email_draft", ""), language="markdown")
                            
                        elif node_name == "spam_checker":
                            is_spam = state_update.get("is_spam", False)
                            if is_spam:
                                st.warning("⚠️ Email looks like spam. Sending back for a rewrite...")
                            else:
                                st.success("✅ Email passed the spam filter!")
                                
            st.balloons()
            st.subheader("🎉 Final Result:")
            # Display the saved final email
            if final_email:
                st.markdown("### Ready-to-send Email:")
                st.write(final_email)
            else:
                st.warning("No email was generated.")
                
        except Exception as e:
            st.error(f"An error occurred during agent execution: {e}")
            st.info("Please check if your API keys are correctly set in the .env file (OPENAI_API_KEY and TAVILY_API_KEY).")
