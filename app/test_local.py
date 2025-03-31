# test_local.py
import asyncio
import os
from dotenv import load_dotenv

from app.services import SolicitationService

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# Provide a path to a local PDF or DOC
test_file_path = "/Users/eliasbrown/Desktop/Capstone/data/GoodFit/IETSS DRAFT PWS v2 for RFI FINAL to POST (1).pdf.md"
# test_file_path = "../Capstone/data/GoodFit/EST Attachment 1 PWS.pdf"
# We'll mimic what your DocumentLoader does, but just for local usage.


class MockUploadFile:
    def __init__(self, filename, file_bytes):
        self.filename = filename
        self._file_bytes = file_bytes

    async def read(self):
        return self._file_bytes


async def run_test():
    with open(test_file_path, "rb") as f:
        content = f.read()

    mock_file = MockUploadFile(test_file_path, content)

    service = SolicitationService(api_key)
    summarized_sections = await service.summarize_document(mock_file)

    # Print result to console
    for sec in summarized_sections:
        print("=== Heading:", sec["heading"], "===")
        print(sec["summary"], "\n")

if __name__ == "__main__":
    asyncio.run(run_test())
