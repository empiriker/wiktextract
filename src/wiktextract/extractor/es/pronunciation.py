import re
import string
from collections import defaultdict
from typing import List

from wikitextprocessor import WikiNode

from wiktextract.extractor.es.models import Sound, Spelling, WordEntry
from wiktextract.extractor.share import create_audio_url_dict
from wiktextract.page import clean_node
from wiktextract.wxr_context import WiktextractContext


def group_and_subgroup_keys(data):
    pattern = re.compile(r"(\d*)(\D+)(\d*)")

    grouped = defaultdict(lambda: defaultdict(list))

    for key in data.copy().keys():
        if isinstance(key, str):
            match = pattern.match(key)
            if match:
                initial_digit = match.group(1) or "0"
                last_digit = match.group(3) or "1"
                grouped[initial_digit][last_digit].append(key)

        elif isinstance(key, int) and key == 1:
            data["fone"] = data[key]
            grouped["0"]["1"].append("fone")

    return grouped


def process_pron_graf_template(
    wxr: WiktextractContext, page_data: List[WordEntry], template_node: WikiNode
) -> None:
    # https://es.wiktionary.org/wiki/Plantilla:pron-graf
    sound_data: List[Sound] = []
    spelling_data: List[Spelling] = []

    sound_keys_grouped = group_and_subgroup_keys(
        template_node.template_parameters
    )

    for sound_keys in sound_keys_grouped.values():
        sound = Sound()
        for variant_keys in sound_keys.values():
            spelling_g = Spelling(
                same_pronunciation=True
            )  # Collect different grafía
            spelling_v = Spelling(
                same_pronunciation=False
            )  # Collect different variants
            for key in variant_keys:
                key_plain = key.strip(string.digits)
                value_raw = template_node.template_parameters.get(key)
                value = clean_node(wxr, {}, value_raw).strip()
                if key_plain == "fone" and value != "...":
                    sound.ipa.append(value)
                elif key_plain == "fono":
                    sound.phonetic_transcription.append(value)
                elif key_plain == "tl":
                    sound.roman.append(value)
                elif key_plain == "ts":
                    sound.syllabic.append(value)
                elif key_plain == "pron":
                    if value != "no":
                        sound.tag.append(value)

                elif key_plain == "audio":
                    audio_url_dict = create_audio_url_dict(value)

                    for key, dict_value in audio_url_dict.items():
                        if dict_value:
                            sound[key].append(dict_value)

                elif key_plain in ["g", "ga", "grafía alternativa"]:
                    spelling_g.alternative = value
                elif key_plain == "gnota":
                    spelling_g.note = value
                elif key_plain in ["v", "variante"]:
                    spelling_v.alternative = value

                elif key_plain == "vnota":
                    spelling_v.note = value
                elif not key in ["leng"]:
                    wxr.wtp.debug(
                        f"Skipped extracting key {key} from pron-graf template",
                        sortid="wiktextract/extractor/es/pronunciation/extract_pronunciation/77",
                    )

            if len(spelling_g.dict(exclude_defaults=True)) > 1:
                spelling_data.append(spelling_g)

            if len(spelling_v.dict(exclude_defaults=True)) > 1:
                spelling_data.append(spelling_v)
        if sound.dict(exclude_defaults=True):
            sound_data.append(sound)

    page_data[-1].sounds = sound_data
    page_data[-1].spellings = spelling_data
