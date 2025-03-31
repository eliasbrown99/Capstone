from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered

config = {
    "output_format": "markdown",
    "OPENAI_API_KEY": "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"
}

config_parser = ConfigParser(config)


def main():
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    rendered = converter(
        filepath="/Users/eliasbrown/Desktop/Capstone/data/GoodFit/IETSS DRAFT PWS v2 for RFI FINAL to POST.pdf")
    text, _, images = text_from_rendered(rendered)
    print(text)


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()  # Safe to include for Windows/macOS compatibility
    main()
