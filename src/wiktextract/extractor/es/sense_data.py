from wikitextprocessor import NodeKind, WikiNode

from wiktextract.extractor.es.example import process_example_list
from wiktextract.extractor.es.linkage import process_linkage_list_children
from wiktextract.extractor.es.models import Sense
from wiktextract.page import clean_node
from wiktextract.wxr_context import WiktextractContext


def process_sense_data_list(
    wxr: WiktextractContext,
    sense_data: Sense,
    list_node: WikiNode,
):
    list_marker = list_node.sarg

    if list_marker == ":;":
        # XXX: Extract subsenses (rare!)
        pass
    elif list_marker in [":*"]:
        for list_item in list_node.find_child(NodeKind.LIST_ITEM):
            children = list(list_item.filter_empty_str_child())
            # The first child will specify what data is listed
            list_type = (
                clean_node(wxr, {}, children[0])
                .strip()
                .removesuffix(":")
                .removesuffix("s")
                .lower()
            )

            if list_type == "ejemplo":
                process_example_list(wxr, sense_data, list_item)
            elif list_type in wxr.config.LINKAGE_SUBTITLES:
                process_linkage_list_children(wxr, sense_data, children[1:])
            elif list_type == "ámbito":
                # XXX: Extract scope tag
                pass
            elif list_type == "uso":
                # XXX: Extract usage note
                pass
            else:
                wxr.wtp.debug(
                    f"Found unknown list type '{list_type}' in {list_item}",
                    sortid="extractor/es/sense_data/process_sense_data_list/46",
                )

    elif list_marker in ["::", ":::"]:
        # E.g. https://es.wiktionary.org/wiki/silepsis
        for list_item in list_node.find_child_recursively(NodeKind.LIST_ITEM):
            process_example_list(wxr, sense_data, list_item)

    else:
        wxr.wtp.debug(
            f"Found unknown list marker {list_marker} in: {list_node}",
            sortid="extractor/es/sense_data/process_sense_data_list/52",
        )
