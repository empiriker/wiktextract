import copy
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from wikitextprocessor import NodeKind, WikiNode
from wikitextprocessor.parser import TemplateNode

from wiktextract.datautils import append_base_data
from wiktextract.extractor.ru.models import PydanticLogger, WordEntry
from wiktextract.page import LEVEL_KINDS, clean_node
from wiktextract.wxr_context import WiktextractContext

# Templates that are used to form panels on pages and that
# should be ignored in various positions
PANEL_TEMPLATES = set()

# Template name prefixes used for language-specific panel templates (i.e.,
# templates that create side boxes or notice boxes or that should generally
# be ignored).
PANEL_PREFIXES = set()

# Additional templates to be expanded in the pre-expand phase
ADDITIONAL_EXPAND_TEMPLATES = set()


def parse_page(
    wxr: WiktextractContext, page_title: str, page_text: str
) -> List[Dict[str, str]]:
    if wxr.config.verbose:
        logging.info(f"Parsing page: {page_title}")
        # Pass current wiktextractcontext to pydantic for more better logging
        PydanticLogger.wxr = wxr

    wxr.config.word = page_title
    wxr.wtp.start_page(page_title)

    # Parse the page, pre-expanding those templates that are likely to
    # influence parsing
    tree = wxr.wtp.parse(
        page_text,
        pre_expand=True,
        additional_expand=ADDITIONAL_EXPAND_TEMPLATES,
    )

    page_data: List[WordEntry] = []
    for level1_node in tree.find_child(NodeKind.LEVEL1):
        for subtitle_template in level1_node.find_content(NodeKind.TEMPLATE):
            lang_code = (
                subtitle_template.template_name.strip()
                .removeprefix("-")
                .removesuffix("-")
            )

            if (
                wxr.config.capture_language_codes is not None
                and lang_code not in wxr.config.capture_language_codes
            ):
                continue

            categories_and_links = defaultdict(list)

            lang_name = clean_node(wxr, categories_and_links, subtitle_template)
            wxr.wtp.start_section(lang_name)

            base_data = WordEntry(
                lang_name=lang_name, lang_code=lang_code, word=wxr.wtp.title
            )
            base_data.update(categories_and_links)
            page_data.append(copy.deepcopy(base_data))

            for non_level2_node in level1_node.invert_find_child(
                NodeKind.LEVEL2
            ):
                wxr.wtp.debug(
                    f"Found unexpected child in level node {level1_node.largs}: {non_level2_node}",
                    sortid="extractor/es/page/parse_page/80",
                )

            for level2_node in level1_node.find_child(NodeKind.LEVEL2):
                print(level2_node.largs)

    return [d.model_dump(exclude_defaults=True) for d in page_data]


# https://ru.wiktionary.org/wiki/Викисловарь:Правила_оформления_статей
