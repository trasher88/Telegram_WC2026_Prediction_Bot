import asyncio

import aiohttp

from config import API_TOKEN


async def test():
    headers = {"X-Auth-Token": API_TOKEN}
    url = "https://api.football-data.org/v4/competitions/WC/matches"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print("STATUS:", response.status)
            text = await response.text()
            print(text[:3000])


if __name__ == "__main__":
    asyncio.run(test())
