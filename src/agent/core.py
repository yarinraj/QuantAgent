import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from src.data.market_data import MarketDataEngine
from src.risk.risk_engine import RiskEngine

load_dotenv()

class QuantAgent:
    """
    AI Advisor Agent powered by Groq API (Llama-3.3-70B) and ReAct loop.
    Coordinates market data retrieval, risk guardrails evaluation, and trade recommendations.
    """

    def __init__(self):
        load_dotenv()
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY is missing from .env file.")

        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key
        )
        self.model = "qwen/qwen3.8-27b"
        self.data_engine = MarketDataEngine()
        self.risk_engine = RiskEngine()
        
    def get_tools_definition(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_summary",
                    "description": "Fetch real-time stock price and technical indicators.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock symbol, e.g. NVDA, AAPL, TSLA"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "evaluate_risk_guardrails",
                    "description": "Evaluates a proposed trade against quantitative risk guardrails.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock symbol"},
                            "proposed_trade_value": {"type": "number", "description": "Trade dollar amount"}
                        },
                        "required": ["symbol", "proposed_trade_value"]
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, args: dict, portfolio_value: float = 10000.0) -> str:
        try:
            if tool_name == "get_market_summary":
                symbol = args.get("symbol", "NVDA")
                summary = self.data_engine.get_market_summary(symbol)
                return json.dumps(summary)

            elif tool_name == "evaluate_risk_guardrails":
                symbol = args.get("symbol", "NVDA")
                trade_val = float(args.get("proposed_trade_value", 0))
                portfolio_val = float(portfolio_value)

                raw_df = self.data_engine.fetch_historical_data(symbol)

                if raw_df is None or raw_df.empty or 'Close' not in raw_df.columns:
                    return json.dumps({
                        "status": "REJECTED",
                        "violations": [f"System safeguard: No valid market data found for '{symbol}'."],
                        "is_approved": False
                    })
                
                df = self.data_engine.add_technical_indicators(raw_df)
                summary = self.data_engine.get_market_summary(symbol)

                evaluation = self.risk_engine.evaluate_risk_guardrails(
                    market_summary=summary,
                    price_series=df['Close'],
                    daily_returns=df['Daily_Return'],
                    proposed_trade_value=trade_val,
                    total_portfolio_value=portfolio_val
                )
                return json.dumps(evaluation)

            return json.dumps({"error": f"Unknown tool name: {tool_name}"})
            
        except Exception as e:
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    def run_advisor_agent(self, user_prompt: str, portfolio_value: float = 10000.0, chat_history: list = None, active_symbol: str = None) -> dict:
        system_instruction = """
        ROLE: You are QuantAgent, a quantitative risk co-pilot for investors. You help users understand risk; you do not make final decisions for them.
        LANGUAGE: Reply in the language the user writes in.
        INTENT: Infer company names/tickers from context ('tesla' -> TSLA). Silently fix minor typos. 
        TOOLS:
        1. Stock question without a trade amount -> call get_market_summary only, give a short view, and ask how much they plan to invest.
        2. Call evaluate_risk_guardrails only when you have BOTH a ticker and an investment amount.
        SAFETY: Never promise returns. Briefly note once per conversation that this is an analytical tool, not licensed financial advice.
        FORMAT & STYLE: 
        - Usually 2-4 sentences or bullets. No markdown headings (#). 
        - Format currency cleanly as '$2,500' or '2,500 USD' (NEVER write 'USD 2,500').
        CRITICAL RISK EVALUATION RULES:
        1. Base your final answer strictly on the approval status returned by the RiskEngine tool. NEVER override a REJECTED status.
        2. Every trade evaluation output MUST explicitly contain either the exact token **APPROVED** or **REJECTED** in uppercase bold markdown in the very first sentence.
        Example approved: "Your proposed $2,500 trade in TSLA was **APPROVED** by our risk guardrails..."
        Example rejected: "Your proposed $2,600 trade in TSLA was **REJECTED** by our risk guardrails..."
        """

        messages = [{"role": "system", "content": system_instruction}]

        if chat_history:
            for msg in chat_history:
                if msg["role"] in ["user", "assistant"]:
                    messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": f"{user_prompt} (Available Portfolio Cash: {portfolio_value:,.2f} USD)"})

        trace_log = []

        for iteration in range(1, 6):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.get_tools_definition(),
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=500,
                )

                response_msg = response.choices[0].message
                messages.append(response_msg)

                if response_msg.tool_calls:
                    for tool_call in response_msg.tool_calls:
                        fn_name = tool_call.function.name
                        
                        try:
                            fn_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"error": "Invalid JSON parameters."})})
                            continue

                        trace_log.append({
                            "iteration": iteration,
                            "action": "TOOL_CALL",
                            "tool": fn_name,
                            "args": fn_args
                        })

                        tool_result_str = self.execute_tool(fn_name, fn_args, portfolio_value=portfolio_value)
                        
                        try:
                            tool_result_dict = json.loads(tool_result_str)
                        except json.JSONDecodeError:
                            tool_result_dict = {"error": "Failed to parse tool output."}

                        if "error" in tool_result_dict:
                            return {
                                "final_answer": f"🔧 **DEBUG ERROR (Tool):** {tool_result_dict['error']}",
                                "trace_log": trace_log
                            }

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result_str
                        })
                else:
                    return {
                        "final_answer": response_msg.content,
                        "trace_log": trace_log
                    }
                    
            except Exception as e:
                return {
                    "final_answer": f"🛑 **DEBUG ERROR (Agent Loop):** {str(e)}",
                    "trace_log": trace_log
                }

        return {
            "final_answer": "Agent reached maximum iteration limit without a final conclusion.",
            "trace_log": trace_log
        }