import os

# Must be set before any module imports settings = Settings()
os.environ.setdefault("WORKSPACE_ID", "test-workspace")
os.environ.setdefault("TG_BOT_TOKEN", "123456:test-bot-token")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("PUBSUB_VERIFICATION_AUDIENCE", "https://test.example.com")
