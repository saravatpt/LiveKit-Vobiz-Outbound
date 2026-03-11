import asyncio
import os
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv(".env")

async def main():
    import sys

    lkapi = api.LiveKitAPI()
    sip = lkapi.sip

    address = os.getenv("VOBIZ_SIP_DOMAIN")
    username = os.getenv("VOBIZ_USERNAME")
    password = os.getenv("VOBIZ_PASSWORD")
    number = os.getenv("VOBIZ_OUTBOUND_NUMBER")

    # --list: show existing trunks
    if "--list" in sys.argv:
        try:
            res = await sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
            if not res.items:
                print("No outbound trunks found.")
            for t in res.items:
                print(f"  ID: {t.sip_trunk_id}  Address: {t.address}  Numbers: {t.numbers}")
        except Exception as e:
            print(f"Failed to list trunks: {e}")
        finally:
            await lkapi.aclose()
        return

    trunk_id = os.getenv("OUTBOUND_TRUNK_ID")

    # If trunk_id exists, try to update; otherwise create new
    if trunk_id:
        print(f"Attempting to update SIP Trunk: {trunk_id}")
        try:
            await sip.update_outbound_trunk_fields(
                trunk_id,
                address=address,
                auth_username=username,
                auth_password=password,
                numbers=[number] if number else [],
            )
            print("SIP Trunk updated successfully!")
            await lkapi.aclose()
            return
        except Exception as e:
            print(f"Update failed ({e}), will create a new trunk instead...")

    # Create a new outbound trunk
    print(f"Creating new outbound SIP trunk...")
    print(f"  Address: {address}")
    print(f"  Username: {username}")
    print(f"  Number: {number}")
    try:
        trunk = await sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    address=address,
                    auth_username=username,
                    auth_password=password,
                    numbers=[number] if number else [],
                    name="Vobiz Outbound Trunk",
                )
            )
        )
        print(f"SIP Trunk created successfully!")
        print(f"  Trunk ID: {trunk.sip_trunk_id}")
        print(f"\n  --> Update OUTBOUND_TRUNK_ID in your .env to: {trunk.sip_trunk_id}")
    except Exception as e:
        print(f"Failed to create trunk: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())
