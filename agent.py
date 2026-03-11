import logging
import os
import json
from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    google,
    noise_cancellation,
    silero,
)
from livekit.agents import llm
from typing import Annotated, Optional

# Load environment variables
load_dotenv(".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")


# TRUNK ID - This needs to be set after you crate your trunk
# You can find this by running 'python setup_trunk.py --list' or checking LiveKit Dashboard
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")
SIP_DOMAIN = os.getenv("VOBIZ_SIP_DOMAIN") 


def _build_tts():
    """Configure the Text-to-Speech provider."""
    logger.info("Using Google TTS")
    return google.TTS(
        credentials_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )



def build_transfer_tool(ctx: agents.JobContext, phone_number: str = None):
    """Build a transfer_call function tool with the job context captured via closure."""

    @llm.function_tool(description="Transfer the call to a human support agent or another phone number.")
    async def transfer_call(destination: Optional[str] = None):
        if destination is None:
            destination = os.getenv("DEFAULT_TRANSFER_NUMBER")
            if not destination:
                return "Error: No default transfer number configured."
        if "@" not in destination:
            if SIP_DOMAIN:
                clean_dest = destination.replace("tel:", "").replace("sip:", "")
                destination = f"sip:{clean_dest}@{SIP_DOMAIN}"
            else:
                if not destination.startswith("tel:") and not destination.startswith("sip:"):
                    destination = f"tel:{destination}"
        elif not destination.startswith("sip:"):
            destination = f"sip:{destination}"

        logger.info(f"Transferring call to {destination}")

        participant_identity = None
        if phone_number:
            participant_identity = f"sip_{phone_number}"
        else:
            for p in ctx.room.remote_participants.values():
                participant_identity = p.identity
                break

        if not participant_identity:
            logger.error("Could not determine participant identity for transfer")
            return "Failed to transfer: could not identify the caller."

        try:
            logger.info(f"Transferring participant {participant_identity} to {destination}")
            await ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=ctx.room.name,
                    participant_identity=participant_identity,
                    transfer_to=destination,
                    play_dialtone=False
                )
            )
            return "Transfer initiated successfully."
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return f"Error executing transfer: {e}"

    return transfer_call


class OutboundAssistant(Agent):

    """
    An AI agent tailored for outbound calls.
    Attempts to be helpful and concise.
    """
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are a helpful and professional voice assistant calling from Vobiz.
            
            Key behaviors:
            1. Introduce yourself clearly when the user answers.
            2. Be concise and respect the user's time.
            3. If asked, explain you are an AI assistant helping with a test call.
            4. If the user asks to be transferred, call the transfer_call tool immediately.
               If no number is specified, do NOT ask for one; just call the tool with the default.
            """
        )


async def entrypoint(ctx: agents.JobContext):
    """
    Main entrypoint for the agent.
    
    For outbound calls:
    1. Checks for 'phone_number' in the job metadata.
    2. Connects to the room.
    3. Initiates the SIP call to the phone number.
    4. Waits for answer before speaking.
    """
    logger.info(f"Connecting to room: {ctx.room.name}")
    
    # parse the phone number from the metadata sent by the dispatch script
    phone_number = None
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
    except Exception:
        logger.warning("No valid JSON metadata found. This might be an inbound call.")

    # Build transfer tool
    transfer_tool = build_transfer_tool(ctx, phone_number)

    # Initialize the Agent Session with plugins
    session = AgentSession(
        stt=google.STT(
            credentials_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        ),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=_build_tts(),
        vad=silero.VAD.load(),
        tools=[transfer_tool],
    )

    # Start the session
    await session.start(
        room=ctx.room,
        agent=OutboundAssistant(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True, # Close room when agent disconnects
        ),
    )

    if phone_number:
        logger.info(f"Initiating outbound SIP call to {phone_number}...")
        try:
            # Create a SIP participant to dial out
            # This effectively "calls" the phone number and brings them into this room
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}", # Unique ID for the SIP user
                    wait_until_answered=True, # Important: Wait for pickup before continuing
                )
            )
            logger.info("Call answered! Agent is now listening.")
            
            # Note: We do NOT generate an initial reply here immediately.
            # Usually for outbound, we want to hear "Hello?" from the user first,
            # OR we can speak immediately. 
            # If you want the agent to speak first, uncomment the lines below:
            
            # await session.generate_reply(
            #     instructions="The user has answered. Introduce yourself immediately."
            # )
            
        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            # Ensure we clean up if the call fails
            ctx.shutdown()
    else:
        # Fallback for inbound calls (if this agent is used for that)
        logger.info("No phone number in metadata. Treating as inbound/web call.")
        await session.generate_reply(instructions="Greet the user.")


if __name__ == "__main__":
    # The agent name "outbound-caller" is used by the dispatch script to find this worker
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller", 
        )
    )
