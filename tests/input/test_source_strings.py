"""Pure lexer: string literals and comment stripping of Kotlin, Java and Gradle text (static-check-spec §5.1)."""

import pytest

from apkverify.input.source_strings import literals, strip_comments

CASES = (
    ('f(configName = "home_bottom", spaceName = "home_bottom_native")', ".kt", ["home_bottom", "home_bottom_native"]),
    ('// "line"\n"kept"', ".kt", ["kept"]),
    ('/* "block" */ "kept"', ".java", ["kept"]),
    ('/* a /* nested */ "still comment" */ "kept"', ".kt", ["kept"]),
    ('/* a /* not nested in java */ "code"', ".java", ["code"]),
    ('"a\\"b\\\\c\\n\\u0041\\$d"', ".kt", ['a"b\\c\nA$d']),
    ('"x_${listOf("inner").first()}_y"', ".kt", ["x_", "inner", "_y"]),
    ('"pre_$name.suffix"', ".kt", ["pre_", ".suffix"]),
    ('"cost $ 5"', ".kt", ["cost $ 5"]),
    ('"price$x"', ".java", ["price$x"]),
    ('"""raw "quoted" ${n} end"""', ".kt", ['raw "quoted" ', " end"]),
    ('"""ends with quote""""', ".kt", ['ends with quote"']),
    ('char q = \'"\'; String s = "after";', ".java", ['"', "after"]),
    ("implementation 'com.example:lib:1.0' // 'gone'", ".gradle", ["com.example:lib:1.0"]),
    ('"$version-${suffix}"', ".gradle", ["-"]),
    ('"unterminated\nval x = "next"', ".kt", ["unterminated", "next"]),
    ('"""never closed', ".kt", ["never closed"]),
    ('"" + "x"', ".kt", ["x"]),
    ("val map = mapOf(1 to 2) }", ".kt", []),
    ('String s = """\n  a \\""" b\n  """; String t = "after";', ".java", ['\n  a """ b\n  ', "after"]),
    ('val s = """a \\""" + "b"', ".kt", ["a \\", "b"]),
)


@pytest.mark.parametrize("text,suffix,expected", CASES)
def test_literals(text: str, suffix: str, expected: list[str]) -> None:
    assert literals(text, suffix) == expected


def test_strip_comments_keeps_strings_and_lines() -> None:
    text = 'maven { url = "https://jitpack.io" } // repo\n/* include(":old")\n */include(":app")'
    assert strip_comments(text, ".kts") == 'maven { url = "https://jitpack.io" }  \n \ninclude(":app")'


def test_strip_comments_keeps_the_line_after_a_block_comment() -> None:
    assert (
        strip_comments('versionCode = 3 /* b\n */ versionName = "1.0"', ".kts")
        == 'versionCode = 3  \n versionName = "1.0"'
    )


def test_comment_inside_template_is_stripped() -> None:
    assert strip_comments('"a${ /* c */ b}"', ".kt") == '"a${   b}"'
