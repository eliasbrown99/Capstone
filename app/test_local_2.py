# test_local.py
import asyncio
import os
from dotenv import load_dotenv

from app.summarization import detect_headings_and_summarize

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

file_path = '/Users/eliasbrown/Desktop/Capstone/data/GoodFit/Attachment A - Statement of Work_July 2023.pdf.md'


async def run_test():
    # 1) Read preprocessed text from a .txt file
    with open(file_path, "r", encoding="utf-8") as f:
        document_text = f.read()

    # 2) Call our summarization function directly
    summarized_sections = await detect_headings_and_summarize(document_text, api_key)

    # 3) Print results to console
    for sec in summarized_sections:
        print("=== Heading:", sec["heading"], "===")
        print(sec["summary"])
        print()

if __name__ == "__main__":
    asyncio.run(run_test())
