# Extracting information from thesaurus pages in Wiktionary.  The data will be
# merged into word linkages in later stages.
#
# Copyright (c) 2021 Tatu Ylonen.  See file LICENSE and https://ylonen.org

import logging
import re
from typing import (
    Optional,
    TYPE_CHECKING,
    Union,
)

from mediawiki_langcodes import code_to_name, name_to_code
from wikitextprocessor import NodeKind, Page, WikiNode
from wikitextprocessor.core import NamespaceDataEntry
from wiktextract.datautils import ns_title_prefix_tuple
from wiktextract.form_descriptions import parse_sense_qualifier
from wiktextract.page import LEVEL_KINDS, clean_node
from wiktextract.thesaurus import ThesaurusTerm
from wiktextract.wxr_context import WiktextractContext

IGNORED_SUBTITLE_TAGS_MAP: dict[str, list[str]] = {
    "by reason": [],
    "by period of time": [],
    "by degree": [],
    "by type": [],
    "other": [],
    "opaque slang terms": ["slang"],
    "slang": ["slang"],
    "colloquial, archaic, slang": ["colloquial", "archaic", "slang"],
    "euphemisms": ["euphemism"],
    "colloquialisms": ["colloquial"],
    "colloquialisms or slang": ["colloquial"],
    "technical terms misused": ["colloquial"],
    "people": [],
    "proper names": ["proper-noun"],
    "race-based (warning- offensive)": ["offensive"],
    "substance addicts": [],
    "non-substance addicts": [],
    "echoing sounds": [],
    "movement sounds": [],
    "impacting sounds": [],
    "destructive sounds": [],
    "noisy sounds": [],
    "vocal sounds": [],
    "miscellaneous sounds": [],
    "age and gender": [],
    "breeds and types": [],
    "by function": [],
    "wild horses": [],
    "body parts": [],
    "colors, patterns and markings": [],
    "diseases": [],
    "equipment and gear": [],
    "groups": [],
    "horse-drawn vehicles": [],
    "places": [],
    "sports": [],
    "sounds and behavior": [],
    "obscure derivations": [],
    "plants": [],
    "animals": [],
    "common": [],
    "rare": ["rare"],
}


def extract_thesaurus_page(
    wxr: WiktextractContext, page: Page
) -> Optional[list[ThesaurusTerm]]:
    """Extracts linkages from the thesaurus pages in Wiktionary."""

    thesaurus_ns_data: NamespaceDataEntry
    thesaurus_ns_data = wxr.wtp.NAMESPACE_DATA["Thesaurus"]

    thesaurus_ns_local_name = thesaurus_ns_data["name"]

    title = page.title
    text = page.body
    assert text is not None
    if title.startswith("Thesaurus:Requested entries "):
        return None
    if "/" in title:
        # print("STRANGE TITLE:", title)
        return None
    word = title[len(thesaurus_ns_local_name) + 1 :]
    idx = word.find(":")
    if idx > 0 and idx < 5:
        word = word[idx + 1 :]  # Remove language prefix
    expanded = wxr.wtp.expand(text, templates_to_expand=None)  # Expand all
    expanded = re.sub(
        r'(?s)<span class="tr Latn"[^>]*>(<b>)?(.*?)(</b>)?' r"</span>",
        r"XLITS\2XLITE",
        expanded,
    )
    tree = wxr.wtp.parse(expanded, pre_expand=False)
    assert tree.kind == NodeKind.ROOT
    lang = None
    pos = None
    sense = None
    linkage = None
    subtitle_tags = []
    entry_id = -1
    # Some pages don't have a language subtitle, but use
    # {{ws header|lang=xx}}
    m = re.search(r"(?s)\{\{ws header\|[^}]*lang=([^}|]*)", text)
    if m:
        lang = code_to_name(m.group(1), "en")

    def recurse(contents) -> Optional[list[ThesaurusTerm]]:
        nonlocal lang
        nonlocal pos
        nonlocal sense
        nonlocal linkage
        nonlocal subtitle_tags
        nonlocal entry_id
        item_sense = None
        tags = None
        topics = None

        if isinstance(contents, (list, tuple)):
            thesaurus = []
            for x in contents:
                x_result = recurse(x)
                if x_result is not None:
                    thesaurus.extend(x_result)
            return thesaurus
        if not isinstance(contents, WikiNode):
            return None
        kind = contents.kind
        if kind == NodeKind.LIST and not contents.contain_node(NodeKind.LIST):
            if lang is None:
                logging.debug(
                    f"{title=} {lang=} UNEXPECTED LIST WITHOUT LANG: "
                    + str(contents)
                )
                return None
            thesaurus = []
            for node in contents.children:
                if isinstance(node, str) or node.kind != NodeKind.LIST_ITEM:
                    continue
                w = clean_node(wxr, None, node.children)
                if "*" in w:
                    logging.debug(f"{title=} {lang=} {pos=} STAR IN WORD: {w}")
                # Check for parenthesized sense at the beginning
                m = re.match(r"(?s)^\(([^)]*)\):\s*(.*)$", w)
                if m:
                    item_sense, w = m.groups()
                    # XXX check for item_sense being part-of-speech
                else:
                    item_sense = sense

                # Remove thesaurus links, if any
                w = re.sub(r"\s*\[W[Ss]\]", "", w)

                # Check for English translation in quotes.  This can be
                # literal translation, not necessarily the real meaning.
                english = None

                def engl_fn(m):
                    nonlocal english
                    english = m.group(1)
                    return ""

                w = re.sub(r'(\bliterally\s*)?(, )?“([^"]*)"\s*', engl_fn, w)

                # Check for qualifiers in parentheses
                tags = []
                topics = []

                def qual_fn(m):
                    q = m.group(1)
                    if q == item_sense:
                        return ""
                    if "XLITS" in q:
                        return q
                    dt = {}
                    parse_sense_qualifier(wxr, q, dt)
                    tags.extend(dt.get("tags", ()))
                    topics.extend(dt.get("topics", ()))
                    return ""

                w = re.sub(r"\(([^)]*)\)$", qual_fn, w).strip()

                # XXX there could be a transliteration, e.g.
                # Thesaurus:老百姓

                # XXX Apparently there can also be alternative spellings,
                # such as 眾人／众人 on Thesaurus:老百姓

                # If the word is now empty or separator, skip
                if not w or w.startswith("---") or w == "\u2014":
                    return None
                rel = linkage or "synonyms"
                for w1 in w.split(","):
                    m = re.match(r"(?s)(.*?)\s*XLITS(.*?)XLITE\s*", w1)
                    if m:
                        w1, xlit = m.groups()
                    else:
                        xlit = None
                    w1 = w1.strip()
                    if w1.startswith(ns_title_prefix_tuple(wxr, "Thesaurus")):
                        w1 = w1[10:]
                    w1 = w1.removesuffix(" [⇒ thesaurus]")

                    if w1:
                        lang_code = name_to_code(lang, "en")
                        if lang_code is None:
                            logging.debug(
                                f"Linkage language {lang} not recognized"
                            )
                        thesaurus.append(
                            ThesaurusTerm(
                                entry=word,
                                language_code=lang_code,
                                pos=pos,
                                linkage=rel,
                                term=w1,
                                tags="|".join(tags) if tags else None,
                                topics="|".join(topics) if topics else None,
                                roman=xlit,
                                sense=item_sense,
                            )
                        )
            return thesaurus
        if kind not in LEVEL_KINDS:
            thesaurus = []
            args_thesaurus = recurse(
                contents.sarg if contents.sarg else contents.largs
            )
            if args_thesaurus is not None:
                thesaurus.extend(args_thesaurus)
            children_thesaurus = recurse(contents.children)
            if children_thesaurus is not None:
                thesaurus.extend(children_thesaurus)
            return thesaurus
        subtitle = wxr.wtp.node_to_text(
            contents.sarg if contents.sarg else contents.largs
        )
        if name_to_code(subtitle, "en") != "":
            lang = subtitle
            pos = None
            sense = None
            linkage = None
            return recurse(contents.children)
        if TYPE_CHECKING:
            assert isinstance(wxr.config.OTHER_SUBTITLES["sense"], str)
        if subtitle.lower().startswith(
            wxr.config.OTHER_SUBTITLES["sense"].lower()
        ):
            sense = subtitle[len(wxr.config.OTHER_SUBTITLES["sense"]) :]
            linkage = None
            return recurse(contents.children)

        subtitle = subtitle.lower()
        if subtitle in (
            "further reading",
            "external links",
            "references",
            "translations",
            "notes",
            "usage",
            "work to be done",
            "quantification",
            "abbreviation",
            "symbol",
        ):
            return None
        if subtitle in wxr.config.LINKAGE_SUBTITLES:
            linkage = wxr.config.LINKAGE_SUBTITLES[subtitle]
            return recurse(contents.children)
        if subtitle in wxr.config.POS_SUBTITLES:
            pos = wxr.config.POS_SUBTITLES[subtitle]["pos"]
            sense = None
            linkage = None
            return recurse(contents.children)
        if subtitle in IGNORED_SUBTITLE_TAGS_MAP:
            # These subtitles are ignored but children are processed and
            # possibly given additional tags
            subtitle_tags = IGNORED_SUBTITLE_TAGS_MAP[subtitle]
            return recurse(contents.children)
        logging.debug(
            f"{title=} {lang=} {pos=} {sense=} UNHANDLED SUBTITLE: "
            + "subtitle "
            + str(contents.sarg if contents.sarg else contents.largs)
        )
        return recurse(contents.children)

    return recurse(tree)
