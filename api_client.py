import httpx
from config import API_TOKEN


class APIClient:
    BASE_URL = "https://api.football-data.org/v4"

    async def get_matches(self):
        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.get(
                f"{self.BASE_URL}/competitions/WC/matches",
                headers={
                    "X-Auth-Token": API_TOKEN
                }
            )
            print("STATUS:", response.status_code)

            if response.status_code != 200:
                print("ERROR RESPONSE:")
                print(response.text)
                return None

            data = response.json()

            print("MATCHES FOUND:", len(data.get("matches", [])))

            return data