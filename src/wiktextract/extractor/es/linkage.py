from typing import Union

from wikitextprocessor import NodeKind, WikiNode
from wikitextprocessor.parser import WikiNodeChildrenList

from wiktextract.extractor.es.models import Linkage, Sense, WordEntry
from wiktextract.page import clean_node
from wiktextract.wxr_context import WiktextractContext


def extract_linkage(
    wxr: WiktextractContext,
    data_container: Union[WordEntry, Sense],
    node: WikiNode,
    linkage_type: str,
):
    for link_node in node.find_child_recursively(NodeKind.LINK):
        word = clean_node(wxr, {}, link_node)
        if word:
            data_container[linkage_type].append(Linkage(word=word))

    for template_node in node.find_child_recursively(NodeKind.TEMPLATE):
        if template_node.template_name == "l":
            word = clean_node(wxr, {}, template_node)
            if word:
                data_container[linkage_type].append(Linkage(word=word))


def process_linkage_template(
    wxr: WiktextractContext,
    data_container: Union[WordEntry, Sense],
    template_node: WikiNode,
):
    linkage_type = wxr.config.LINKAGE_SUBTITLES.get(
        template_node.template_name.removesuffix("s")
    )
    for key, value_raw in template_node.template_parameters.items():
        value = clean_node(wxr, {}, value_raw)
        if isinstance(key, int):
            data_container[linkage_type].append(Linkage(word=value))
        elif isinstance(key, str):
            if key.startswith("nota"):
                idx = int(key[4:]) - 1 if len(key) > 4 else 0

                if len(data_container[linkage_type]) > idx:
                    data_container[linkage_type][idx].note = value

            elif key.startswith("alt"):
                idx = int(key[3:]) - 1 if len(key) > 3 else 0

                if len(data_container[linkage_type]) > idx:
                    data_container[linkage_type][
                        idx
                    ].alternative_spelling = value


def process_linkage_list_children(
    wxr: WiktextractContext,
    data_container: Union[WordEntry, Sense],
    nodes: WikiNodeChildrenList,
    linkage_type: str,
):
    for node in nodes:
        if isinstance(node, WikiNode) and node.kind == NodeKind.LINK:
            word = clean_node(wxr, {}, node)
            if word:
                data_container[linkage_type].append(Linkage(word=word))
