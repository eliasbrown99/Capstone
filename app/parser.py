from llama_index.core import SimpleDirectoryReader
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv
import os

load_dotenv()

# Set up parser
parser = LlamaParse(
    result_type="markdown",
    parse_mode="parse_page_with_layout_agent",
    html_remove_navigation_elements=True,
    preserve_layout_alignment_across_pages=True,
    extract_layout=True,
    system_prompt=""" 
        Items which look like document titles, dates, table of contents, etc should be completely eliminated from the output.
        Only output section, subsection, subsubsection, etc -titles, narrative text, list elements, and table elements.
        Be sure to capture to the best of your ability the differences between section titles and subsection titles and denote this in markdown.
        Key remark: all top level headings (i.e., single # in markdown) will be those that start with a number followed by either a period or a period and a zero.""",
    system_prompt_append="""
        Though not a rigid rule, bold text is a better litmus test to deem a line (or lines) as section headers rather than capitalization at the beginning of a
        page, though section headers/titles often are capitalized. Remain "page number agnostic" when deciding on section titles.
        Also elements which look like section titles but are not numbered, should be rendered as subsections.
    """
)

# Read PDF (which may chunk into multiple Document objects)
file_extractor = {".pdf": parser}
documents = SimpleDirectoryReader(
    input_files=["/Users/eliasbrown/Desktop/Capstone/data/GoodFit/EST Attachment 1 PWS.PDF"],
    file_extractor=file_extractor
).load_data()

# Combine the text from all Document objects into one string
all_text = "\n\n".join(doc.text for doc in documents)

# Save the combined Markdown to a single file
output_file = "parsed_output.md"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(all_text)

print(f"Markdown from all chunks saved to {output_file}")
