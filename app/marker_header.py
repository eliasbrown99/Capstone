from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
import re


def is_probable_header(text):
    # Match things like: "1.0 SCOPE", "2.3.1 Requirements", "3 PURPOSE"
    return bool(re.match(r"^\s*\d+(\.\d+)*\s+[A-Z][^\n]+$", text.strip()))


def main():
    converter = PdfConverter(
        artifact_dict=create_model_dict(),  # disable layout model
    )

    rendered = converter(
        filepath="/Users/eliasbrown/Desktop/Capstone/data/GoodFit/IETSS DRAFT PWS v2 for RFI FINAL to POST.pdf")

    text, _, _ = text_from_rendered(rendered)

    print("Probable Section Headers:\n")
    for line in text.splitlines():
        if is_probable_header(line):
            print(line.strip())


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
