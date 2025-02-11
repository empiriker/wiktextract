import unittest

from wikitextprocessor import Wtp

from wiktextract.config import WiktionaryConfig
from wiktextract.extractor.ru.example import process_example_template
from wiktextract.extractor.ru.models import Sense
from wiktextract.wxr_context import WiktextractContext


class TestRUExample(unittest.TestCase):
    def setUp(self) -> None:
        self.wxr = WiktextractContext(
            Wtp(lang_code="ru"),
            WiktionaryConfig(dump_file_lang_code="ru"),
        )

    def tearDown(self) -> None:
        self.wxr.wtp.close_db_conn()

    def get_default_sense_data(self) -> Sense:
        return Sense()

    def test_ru_extract_example(self):
        test_cases = [
            # Ignores empty template
            {"input": "{{пример|}}", "expected": []},
            # https://ru.wiktionary.org/wiki/Красная_Шапочка
            {
                "input": "{{пример|Недолго думая, отправляю овощ в рот.|М. И. Саитов|Островки||Бельские Просторы|2010|источник=НКРЯ}}",
                "expected": [
                    {
                        "ref": {
                            "author": "М. И. Саитов",
                            "collection": "Бельские Просторы",
                            "date_published": "2010",
                            "source": "НКРЯ",
                            "title": "Островки",
                        },
                        "text": "Недолго думая, отправляю овощ в рот.",
                    }
                ],
            },
            # https://ru.wiktionary.org/wiki/house
            {
                "input": "{{пример|This is my house and my family’s ancestral home.||перевод=Это мой дом и поселение моих семейных предков.}}",
                "expected": [
                    {
                        "text": "This is my house and my family’s ancestral home.",
                        "translation": "Это мой дом и поселение моих семейных предков.",
                    }
                ],
            },
        ]

        for case in test_cases:
            with self.subTest(case=case):
                self.wxr.wtp.start_page("")
                sense_data = self.get_default_sense_data()

                root = self.wxr.wtp.parse(case["input"])

                process_example_template(self.wxr, sense_data, root.children[0])

                examples = [
                    e.model_dump(exclude_defaults=True)
                    for e in sense_data.examples
                ]
                self.assertEqual(examples, case["expected"])
