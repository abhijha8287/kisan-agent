from kisan_agent.integrations.tavily import TavilyClient


async def test_uses_bearer_auth_when_key_is_set():
    client = TavilyClient(api_key="tvly-test", timeout_s=5)
    assert client._http.headers["Authorization"] == "Bearer tvly-test"
    assert "X-Tavily-Access-Mode" not in client._http.headers
    await client.aclose()


async def test_falls_back_to_keyless_mode_without_key():
    client = TavilyClient(api_key="", timeout_s=5)
    assert client._http.headers["X-Tavily-Access-Mode"] == "keyless"
    assert "Authorization" not in client._http.headers
    await client.aclose()
