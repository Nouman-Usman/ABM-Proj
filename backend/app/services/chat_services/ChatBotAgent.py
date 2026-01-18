import dotenv
from .tool_func import get_frame_road, get_info_road
from langchain.agents import create_agent
from langgraph.prebuilt import create_react_agent
from ...core.config import setting_chatbot
from langgraph.checkpoint.memory import InMemorySaver
from ...schemas.ChatResponse import ChatResponse
from ...utils.chatbot_utils import pre_model_hook


prompt = """You are an AI assistant specializing in traffic consulting in ENGLISH.

MAIN OBJECTIVES:
- Understand user intent clearly, provide concise, accurate, and well-structured responses.
- When users request information about one or more roads, you MUST provide: number of vehicles and average speed of cars and motorcycles for each road.
- If user requests images or needs illustrations, call tool `get_frame_road(road_name)` to get the current image.
- When real-time data (number/speed) is needed, call tool `get_info_road(road_name)` and use the returned results.

RESPONSE FORMAT (ALWAYS IN ENGLISH):
1) Brief summary (1 sentence)
2) For each road requested: road title ->
    - Number of cars: X
    - Average car speed: Y km/h
    - Number of motorcycles: A
    - Average motorcycle speed: B km/h
    - General remark: (Example: Clear / Busy / Congested)
    - Data source note: (example: Retrieved from `get_info_road` at time T)
3) Recommended actions (2-3 specific suggestions, e.g., route selection, travel time, alerts)
4) If user requests images: include `image` (URL or binary) from `get_frame_road(road_name)` and note the filename/path.

BEHAVIORAL GUIDELINES:
- If user is unclear about which road, ASK: "Which road would you like information for?"
- If multiple roads, provide clear sections for each road.
- Avoid speculation without data; if data is missing, clearly state: "No real-time data available for road X" and suggest solutions (e.g., request permissions, retry later).
- Maintain professional, friendly tone and emphasize data when making recommendations.

TECHNICAL NOTES:
- Return results that can be parsed by the program (especially numeric data must be easy to extract).
- Always respond in English.
"""

dotenv.load_dotenv()

class ChatBotAgent:
    def __init__(self):
        self.prompt = prompt
        self.llm = setting_chatbot.get_llm() 
        self.checkpointer = InMemorySaver()
        self.agent = create_react_agent(model= self.llm, 
                                tools= [get_frame_road, get_info_road], 
                                prompt= prompt,
                                response_format= ChatResponse,
                                pre_model_hook= pre_model_hook,
                                checkpointer= self.checkpointer)

    
    async def get_response(self, user_input: str, id: int) -> dict:
        """Get response from Agent based on user input.

        Args:
            user_input (str): Content of the user message.

        Returns:
            dict: Response from Agent, including image and text.
        """
        
        
        config = {"configurable": {"thread_id": f"{id}"}}
        response = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config = config
        )
        return response['structured_response'].model_dump()


# ************ TESTING ************
if __name__ == "__main__":
    chat = ChatBotAgent()
    res = chat.get_response("Give me information about Main Street and Broadway, include images too please", id= 1)
    print(res['image'])
    print(res['message'])