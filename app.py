import streamlit as st
from src.data.market_data import MarketDataEngine
from src.risk.risk_engine import RiskEngine
from src.agent.core import AIAgentCore

# Page Configuration
st.set_page_config(page_title="QuantAgent | Hybrid UI", page_icon="⚡", layout="wide")

# Initialize Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I am QuantAgent. You can use the Quick Analysis panel on the left, or ask me anything directly in the chat below."}
    ]

# Initialize Agent
@st.cache_resource
def load_agent():
    return AIAgentCore()

ai_agent = load_agent()

# ==========================================
# Sidebar: Quick Analysis & Portfolio State
# ==========================================
st.sidebar.subheader("⚡ Quick Analysis")

target_symbol = st.sidebar.text_input("Stock Symbol", value="NVDA").upper()

proposed_amount = st.sidebar.number_input(
    "Proposed Trade ($)",
    min_value=100.0,
    value=3000.0,
    step=250.0
)

# Hybrid trigger: Button in sidebar
quick_run = st.sidebar.button("🚀 Run AI Analysis", use_container_width=True)

st.sidebar.divider()
st.sidebar.subheader("💼 Portfolio State")
portfolio_cash = st.sidebar.number_input("Available Cash ($)", value=10000.0, step=1000.0)

if st.sidebar.button("Clear Chat"):
    st.session_state.messages = [st.session_state.messages[0]]
    st.rerun()

# ==========================================
# Main Chat Interface
# ==========================================
st.title("QuantAgent Research Chat")
st.divider()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Hybrid Logic: Check if input comes from Chat OR from the Sidebar button
chat_input = st.chat_input("E.g., Analyze TSLA vs AAPL, or what happens if I invest $5000 in MSFT?")

# Determine the active prompt
active_prompt = None
if quick_run:
    active_prompt = f"Please evaluate a ${proposed_amount:,.2f} trade on {target_symbol} based on current metrics."
elif chat_input:
    active_prompt = chat_input

# Execute if there is a prompt
if active_prompt:
    # 1. Append User Message to UI State
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    # 2. AI Processing
    with st.chat_message("assistant"):
        with st.spinner("Agent is analyzing the market..."):
            try:
                agent_result = ai_agent.run_advisor_agent(
                    user_prompt=active_prompt, 
                    portfolio_value=portfolio_cash,
                    chat_history=st.session_state.messages[:-1]  
                )
                # --------------------------------------------------------------------------------
                
                final_answer = agent_result["final_answer"]
                
                # Display output
                st.markdown(final_answer)
                
                # Expandable tool logs
                with st.expander("🔍 View Internal Reasoning"):
                    for log in agent_result["trace_log"]:
                        st.caption(f"**Step {log['iteration']} - {log['action']}**")
                        if log['action'] == 'TOOL_CALL':
                            st.code(f"{log['tool']}({log['args']})", language="json")
                        else:
                            st.json(log['result'])
                
                # 3. Save to history
                st.session_state.messages.append({"role": "assistant", "content": final_answer})
                import streamlit.components.v1 as components
                components.html(
                    """
                    <script>
                        const target = window.parent.document.querySelector('section.main');
                        if (target) {
                            target.scrollTop = target.scrollHeight;
                        }
                    </script>
                    """,
                    height=0
                )
            except Exception as e:
                error_msg = f"An error occurred: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})