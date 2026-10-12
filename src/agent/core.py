import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from src.data.market_data import MarketDataEngine
from src.risk.risk_engine import RiskEngine

load_dotenv()

class AIAgentCore:
    """
    AI Advisor Agent powered by Groq API (Llama-3.3-70B) and ReAct loop.
    Coordinates market data retrieval, risk guardrails evaluation, and trade recommendations.
    """

    def __init__(self):
        load_dotenv()
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY is missing from .env file.")

        # Explicitly configure Groq API endpoint
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key
        )
        # Active model name on Groq
        self.model = "qwen/qwen3.8-27b"
        self.data_engine = MarketDataEngine()
        self.risk_engine = RiskEngine()
        
    def get_tools_definition(self):
        """Returns the JSON schema definitions of tools available to the LLM agent."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_summary",
                    "description": "Fetch real-time stock price and technical indicators (SMA_20, SMA_50, RSI_14, Volatility) for a ticker symbol.",
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
                    "description": "Evaluates a proposed trade against quantitative risk guardrails (Max Drawdown, Sharpe Ratio, RSI limits, Allocation cap).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock symbol"},
                            "proposed_trade_value": {"type": "number", "description": "Trade dollar amount"},
                            "total_portfolio_value": {"type": "number", "description": "Total available portfolio cash/value"}
                        },
                        "required": ["symbol", "proposed_trade_value", "total_portfolio_value"]
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, args: dict) -> str:
        """Executes local Python tools based on agent function calls with global error handling."""
        try:
            if tool_name == "get_market_summary":
                symbol = args.get("symbol", "NVDA")
                summary = self.data_engine.get_market_summary(symbol)
                return json.dumps(summary)

            elif tool_name == "evaluate_risk_guardrails":
                symbol = args.get("symbol", "NVDA")
                trade_val = args.get("proposed_trade_value", 2000.0)
                portfolio_val = args.get("total_portfolio_value", 10000.0)

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
            return json.dumps({"error": f"Tool execution failed due to invalid data: {str(e)}"})

    def run_advisor_agent(self, user_prompt: str, portfolio_value: float = 10000.0, chat_history: list = None) -> dict:
        """
        Executes the ReAct loop with Chat History (Memory) to generate a risk-aware recommendation.
        """
        system_instruction = (
            "You are QuantAgent, a professional Wall Street Quantitative Risk Advisor. "
            "Always inspect market metrics using 'get_market_summary' and evaluate risk guardrails using "
            "'evaluate_risk_guardrails' before issuing a trade recommendation. "
            "If risk guardrails are REJECTED, adjust the proposed trade size or recommend HOLD/WAIT."
        )

        # 1. Initialize with System Prompt
        messages = [{"role": "system", "content": system_instruction}]

        # 2. Inject Memory (Chat History) from previous turns
        if chat_history:
            for msg in chat_history:
                if msg["role"] in ["user", "assistant"]:
                    messages.append({"role": msg["role"], "content": msg["content"]})

        # 3. Add the current prompt with portfolio state
        messages.append({"role": "user", "content": f"{user_prompt} (Available Portfolio Cash: ${portfolio_value:,.2f})"})

        trace_log = []

        for iteration in range(1, 6):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.get_tools_definition(),
                    tool_choice="auto"
                )

                response_msg = response.choices[0].message
                messages.append(response_msg)

                if response_msg.tool_calls:
                    for tool_call in response_msg.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)

                        trace_log.append({
                            "iteration": iteration,
                            "action": "TOOL_CALL",
                            "tool": fn_name,
                            "args": fn_args
                        })

                        # Execute tool and safely load JSON
                        tool_result_str = self.execute_tool(fn_name, fn_args)
                        try:
                            tool_result_dict = json.loads(tool_result_str)
                        except json.JSONDecodeError:
                            tool_result_dict = {"error": "Failed to parse tool output."}

                        trace_log.append({
                            "iteration": iteration,
                            "action": "OBSERVATION",
                            "result": tool_result_dict
                        })

                        # --- SHORT-CIRCUIT: Absolute protection against crashes ---
                        if "error" in tool_result_dict:
                            return {
                                "final_answer": f"System Safeguard: I encountered an issue retrieving valid data for this asset. Please verify the ticker symbol.",
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
                # Catch-all for any LLM or internal agent crashes
                return {
                    "final_answer": f"I apologize, but I encountered an internal error processing that request. Let's try again.",
                    "trace_log": trace_log
                }

        return {
            "final_answer": "Agent reached maximum iteration limit without a final conclusion.",
            "trace_log": trace_log
        }
if __name__ == "__main__":
    agent = AIAgentCore()
    prompt = "Should I buy $3,000 worth of NVDA stock right now?"
    
    print(f"User Prompt: {prompt}\n" + "="*50)
    result = agent.run_advisor_agent(prompt, portfolio_value=10000.0)

    print("\n--- Agent Reasoning Trace ---")
    for log in result["trace_log"]:
        print(f"[{log['action']}] Iteration {log['iteration']}: {log.get('tool', '')} -> {log.get('args', log.get('result'))}")

    print("\n🎯 --- Final Recommendation ---")
    print(result["final_answer"])
    
    