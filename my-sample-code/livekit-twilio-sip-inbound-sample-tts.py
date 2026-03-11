from dotenv import load_dotenv
import os
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import google , silero, noise_cancellation
# from livekit import google,silero,noise_cancellation

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Assuming you have GOOGLE_TTS_MODEL and GOOGLE_TTS_VOICE set in your .env file
# from livekit.plugins.google import TTS


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=os.getenv("HeathcareAssistanceAgentInstruction"))


# async def entrypoint(ctx: agents.JobContext):
#     session = AgentSession(
#         llm=openai.realtime.RealtimeModel(
#             voice="coral"
#         )
#     )

async def entrypoint(ctx: agents.JobContext):
    try:
        # session = AgentSession(
        #     llm=google.beta.realtime.RealtimeModel(
        #         model="gemini-2.0-flash-exp",
        #         vertexai=True,
        #         voice="Puck",
        #         temperature=0.8,
        #         instructions="You are a helpful voice AI assistant.",
        #     ),
        
        # session = AgentSession(
        #         llm=google.beta.realtime.RealtimeModel(
        #         model="gemini-2.0-flash-exp",
        #         vertexai=True,
        #         voice="Puck",
        #         temperature=0.8,
        #         instructions=os.getenv("HeathcareAssistanceAgentInstruction")
        # ))

        session = AgentSession(
        tts=google.TTS(),
        stt=google.STT(),
        llm=google.LLM(model="gemini-2.0-flash"),
        vad=silero.VAD.load(),
        # turn_detection=MultilingualModel(),
    )

        # room=ctx.room,
        # room="my-room",
        # print(f"Agent session started with identity: {session.identity}")
        await ctx.connect()
        print("Agent session starting...")
        await session.start(
            room=ctx.room,
            agent=Assistant(),
            room_input_options=RoomInputOptions(
                # LiveKit Cloud enhanced noise cancellation
                # - If self-hosting, omit this parameter
                # - For telephony applications, use `BVCTelephony` for best results
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
        
        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )
    except Exception as e:
        print(f"Error in entrypoint: {e}", exc_info=True)



# ... your existing agent code ...

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        # agent_name is required for explicit dispatch
        # agent_name="My inbound trunk"
    ))