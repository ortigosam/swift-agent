import asyncio
from copilot import CopilotClient


async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session(
        model="gpt-5.4"
    )

    response = await session.send_and_wait(
        prompt="Dime qué puedes hacer."
    )

    print(response.data.content)

    await client.stop()


asyncio.run(main())