from app import trending_diff


def test_diff_finds_new_entries():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert len(new) == 1
    assert new[0]["full_name"] == "b/y"


def test_diff_empty_today():
    today = {"items": []}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_empty_yesterday():
    today = {"items": [{"full_name": "a/x"}]}
    yesterday = None
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_no_new_when_all_overlap():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []
