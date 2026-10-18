import pytest

from jarvis.facts import Facts, looks_secret


def make(tmp_path):
    return Facts(tmp_path / "f.sqlite3")


def test_a_fact_is_added_and_listed_oldest_first(tmp_path):
    facts = make(tmp_path)

    assert facts.add("my cat is called Mochi") == "added"
    assert facts.add("my sister lives in Bandung") == "added"

    assert facts.all() == ["my cat is called Mochi", "my sister lives in Bandung"]


def test_an_empty_store_lists_nothing(tmp_path):
    assert make(tmp_path).all() == []


def test_the_same_fact_with_other_case_or_spacing_is_a_duplicate(tmp_path):
    facts = make(tmp_path)
    facts.add("My cat is called Mochi")

    assert facts.add("my   CAT is called mochi ") == "duplicate"
    assert facts.all() == ["My cat is called Mochi"]


def test_spacing_is_collapsed_in_the_stored_text(tmp_path):
    facts = make(tmp_path)

    facts.add("  my   cat\tis Mochi \n")

    assert facts.all() == ["my cat is Mochi"]


def test_an_indonesian_fact_round_trips(tmp_path):
    facts = make(tmp_path)

    facts.add("ulang tahun ibuku tanggal 3 Mei")

    assert make(tmp_path).all() == ["ulang tahun ibuku tanggal 3 Mei"]


@pytest.mark.parametrize("length", [3, 200])
def test_facts_of_the_allowed_lengths_are_accepted(tmp_path, length):
    assert make(tmp_path).add("x" * length) == "added"


@pytest.mark.parametrize("length", [0, 2, 201])
def test_facts_outside_the_length_limits_are_refused(tmp_path, length):
    facts = make(tmp_path)

    with pytest.raises(ValueError, match="between 3 and 200 characters"):
        facts.add("x" * length)
    assert facts.all() == []


def test_the_length_is_measured_after_trimming(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path).add("  ab  ")


def test_the_31st_fact_is_refused_and_nothing_is_evicted(tmp_path):
    facts = make(tmp_path)
    for n in range(30):
        facts.add(f"fact number {n}")

    with pytest.raises(ValueError) as error:
        facts.add("one more fact")

    assert str(error.value) == (
        "memory is full (30 facts); ask the user which one to forget"
    )
    assert len(facts.all()) == 30
    assert facts.all()[0] == "fact number 0"


def test_a_duplicate_is_reported_even_when_memory_is_full(tmp_path):
    facts = make(tmp_path)
    for n in range(30):
        facts.add(f"fact number {n}")

    assert facts.add("FACT number 7") == "duplicate"


def test_forgetting_makes_room_again(tmp_path):
    facts = make(tmp_path)
    for n in range(30):
        facts.add(f"fact number {n}")
    facts.remove("number 7")

    assert facts.add("a new fact") == "added"


def test_remove_deletes_every_fact_containing_the_query(tmp_path):
    facts = make(tmp_path)
    facts.add("my cat is called Mochi")
    facts.add("my dog is called Rex")
    facts.add("Mochi eats fish")

    removed = facts.remove("  MOCHI ")

    assert removed == ["my cat is called Mochi", "Mochi eats fish"]
    assert facts.all() == ["my dog is called Rex"]


def test_remove_with_no_match_removes_nothing(tmp_path):
    facts = make(tmp_path)
    facts.add("my cat is called Mochi")

    assert facts.remove("parrot") == []
    assert facts.all() == ["my cat is called Mochi"]


def test_a_removed_fact_can_be_added_again(tmp_path):
    facts = make(tmp_path)
    facts.add("my cat is called Mochi")
    facts.remove("cat")

    assert facts.add("my cat is called Mochi") == "added"


def test_a_query_shorter_than_three_characters_never_removes_anything(tmp_path):
    facts = make(tmp_path)
    facts.add("my cat is called Mochi")

    with pytest.raises(ValueError, match="at least 3 letters"):
        facts.remove("a")
    with pytest.raises(ValueError):
        facts.remove("  ca ")
    assert facts.all() == ["my cat is called Mochi"]


def test_percent_and_underscore_in_a_query_are_plain_characters(tmp_path):
    facts = make(tmp_path)
    facts.add("my cat is called Mochi")

    assert facts.remove("%%%") == []
    assert facts.remove("___") == []
    assert len(facts.all()) == 1


@pytest.mark.parametrize(
    "text",
    [
        "my password is hunter2",
        "my Passwd is x",
        "kata sandi wifi saya adalah kucing",
        "my PIN is 4821",
        "the otp is 123",
        "my token is abc",
        "my API key is abc",
        "api   key is abc",
        "the secret is under the bed",
        "cvv is 123",
    ],
)
def test_secret_words_are_refused(tmp_path, text):
    facts = make(tmp_path)

    assert looks_secret(text)
    with pytest.raises(ValueError) as error:
        facts.add(text)
    assert str(error.value) == "I do not store passwords, keys or card or ID numbers"
    assert facts.all() == []


@pytest.mark.parametrize(
    "text",
    [
        "4111111111111",
        "4111 1111 1111 1111",
        "4111-1111-1111",
        "123456789",
        "id 3171 0123 4567",
    ],
)
def test_nine_or_more_digits_in_a_row_are_refused(text):
    assert looks_secret(text)


@pytest.mark.parametrize(
    "text",
    [
        "12345678",
        "call 1234 5678",
        "my cat is called Mochi",
        "I love spinning classes",
        "rumahku di pinggir kota",
        "my tokenizer is fast",
        "the pinwheel is red",
        "ulang tahun ibuku tanggal 3 Mei",
    ],
)
def test_ordinary_facts_are_not_secret(text):
    assert not looks_secret(text)
