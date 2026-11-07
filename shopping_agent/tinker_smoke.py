
"""Test the Thinking Machines API connection.

This test does not access PostgreSQL or the shopping cart.
It only verifies that the API key and model work.
"""

import os
from getpass import getpass

from anthropic import Anthropic


BASE_URL = (
    "https://tinker.thinkingmachines.dev/"
    "services/tinker-prod/anthropic/api"
)

MODEL = "thinkingmachines/Inkling"


def main():
    # Read the API key from an environment variable,
    # or securely prompt for it in the terminal.
    api_key = os.getenv("TINKER_API_KEY")

    if not api_key:
        api_key = getpass(
            "Enter your Thinking Machines API key: "
        ).strip()

    if not api_key:
        raise ValueError("API key cannot be empty.")

    # Create an Anthropic-compatible Tinker client.
    client = Anthropic(
        base_url=BASE_URL,
        api_key=api_key,
        timeout=45.0,
        max_retries=0,
    )

    print("\nConnecting to Thinking Machines...")

    # Make a small request to verify inference access.
    response = client.messages.create(
        model=MODEL,
        max_tokens=128,
        thinking={"type": "disabled"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Reply with exactly this text: CONNECTION_OK"
                ),
            }
        ],
    )

    print("\n=== CONNECTION RESULT ===")
    print("Model:", response.model)

    for block in response.content:
        if block.type == "text":
            print("Response:", block.text)

    print("\n=== TOKEN USAGE ===")
    print("Input tokens:", response.usage.input_tokens)
    print("Output tokens:", response.usage.output_tokens)


if __name__ == "__main__":
    main()
