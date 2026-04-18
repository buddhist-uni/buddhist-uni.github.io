from pathlib import Path
import tempfile
import os

import strutils
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

def test_approx_eq():
    assert strutils.approx_eq(1.0, 1.0)
    assert strutils.approx_eq(1.0, 1.5, absdiff=0.6)
    assert not strutils.approx_eq(100.0, 105.0, absdiff=1.0, percent=2.0)
    assert strutils.approx_eq(100.0, 102.0, absdiff=1.0, percent=3.0)

def test_sanitize_string():
    assert strutils.sanitize_string("  hello \n world!@#$%^&*()_+ ") == "hello world_"

def test_md5():
    assert strutils.md5(b"test") == "098f6bcd4621d373cade4e832627b4f6"
    assert strutils.md5("test") == "098f6bcd4621d373cade4e832627b4f6"
    
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"test")
        tf.close()
        assert strutils.md5(Path(tf.name)) == "098f6bcd4621d373cade4e832627b4f6"
        os.remove(tf.name)

def test_cumsum():
    assert strutils.cumsum([1, 2, 3]) == [1, 3, 6]

def test_naturally_sorted():
    assert strutils.naturally_sorted(["item10", "item1", "item2"]) == ["item1", "item2", "item10"]

def test_fully_encode_url():
    assert strutils.fully_encode_url("https://example.com/Nibbāna%20and%20Abhidhamma") == "https://example.com/Nibb%C4%81na%20and%20Abhidhamma"

def test_FileSyncedSet():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        fname = tf.name
    
    s = strutils.FileSyncedSet(fname)
    s.add("hello")
    s.add("world")
    assert "hello" in s
    assert len(s) == 2
    
    s2 = strutils.FileSyncedSet(fname)
    assert "hello" in s2
    assert "world" in s2
    
    s2.remove("hello")
    assert "hello" not in s2
    assert len(s2) == 1
    s2.delete_file()

def test_FileSyncedSet_normalizer():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        fname = tf.name
    
    # Test default normalizer (replaces \n with space)
    s = strutils.FileSyncedSet(fname)
    s.add("hello\nworld")
    assert "hello world" in s
    assert "hello\nworld" in s
    assert len(s) == 1
    
    # Test custom normalizer (lowercase)
    s_norm = strutils.FileSyncedSet(fname, normalizer=lambda x: x.lower())
    s_norm.add("HELLO")
    assert "hello" in s_norm
    assert "HELLO" in s_norm
    assert len(s_norm.items) == 2 # "hello world" and "hello"
    
    s_norm.remove("Hello")
    assert "hello" not in s_norm
    os.remove(fname)

def test_FileSyncedMap():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        fname = tf.name
        tf.write(b"{}")
        tf.close()

    m = strutils.FileSyncedMap(fname)
    m.set("key", "value")
    assert m.get("key") == "value"
    assert "key" in m
    assert m["key"] == "value"
    
    m2 = strutils.FileSyncedMap(fname)
    assert m2["key"] == "value"
    m2.delete_file()

def test_FileSyncedMap_normalizer():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        fname = tf.name
        tf.write(b"{}")
        tf.close()

    # Test custom keynormalizer (lowercase)
    m = strutils.FileSyncedMap(fname, keynormalizer=lambda x: x.lower())
    m.set("Key", "Value")
    assert "key" in m
    assert "KEY" in m
    assert m["kEy"] == "Value"
    assert m.get("KEY") == "Value"
    
    m["AnotherKey"] = "AnotherValue"
    assert "anotherkey" in m
    
    # Test update (now uses normalization)
    m.update({"UPPER": "value"})
    assert "upper" in m.items
    assert "UPPER" not in m.items
    
    del m["UPPER"]
    assert "upper" not in m
    
    m.delete_file()

def test_invert_inverted_index():
    index = {"hello": [0, 2], "world": [1]}
    assert strutils.invert_inverted_index(index) == ["hello", "world", "hello"]

def test_authorstr():
    assert strutils.authorstr({"authorships": [{"author": {"display_name": "Smith, John"}}]}) == "John Smith"
    assert strutils.authorstr({"authors": [{"name": "Smith, John"}]}) == "John Smith"
    assert strutils.authorstr({"authors": [{"name": "Smith, John"}, {"name": "Doe, Jane"}, {"name": "Foo, Bar"}]}) == "John Smith, et al"
    assert strutils.authorstr({"authors": [{"name": "Smith, John"}, {"name": "Doe, Jane"}, {"name": "Foo, Bar"}, {"name": "Extra, User"}]}, maxn=3) == "John Smith, Jane Doe, et al"

def test_yt_url_to_id_re():
    # Standard YouTube URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"
    
    # youtu.be short URL
    m = strutils.yt_url_to_id_re.search("https://youtu.be/dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"
    
    # YouTube Embed URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/embed/dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

    # YouTube No-cookie Embed URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

    # YouTube Live URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/live/dQw4w9WgXcQ?feature=share")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

    # YouTube v/ URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/v/dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

    # YouTube attribution URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/attribution_link?a=xyz&u=/watch?v=dQw4w9WgXcQ&feature=share")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

    # YouTube user/channel URL
    m = strutils.yt_url_to_id_re.search("https://www.youtube.com/user/google/dQw4w9WgXcQ")
    assert m is not None
    assert m.group(1) == "dQw4w9WgXcQ"

def test_yt_url_to_plid_re():
    # Standard Playlist URL
    m = strutils.yt_url_to_plid_re.search("https://www.youtube.com/playlist?list=PL3oW2tjiIx0UvWb6e3qzWwpTMTsd-6O3R")
    assert m is not None
    assert m.group(1) == "PL3oW2tjiIx0UvWb6e3qzWwpTMTsd-6O3R"

    # Video + Playlist URL
    m = strutils.yt_url_to_plid_re.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL3oW2tjiIx0UvWb6e3qzWwpTMTsd-6O3R")
    assert m is not None
    assert m.group(1) == "PL3oW2tjiIx0UvWb6e3qzWwpTMTsd-6O3R"

    m = strutils.yt_url_to_plid_re.search("Check out this playlist: https://www.youtube.com/playlist?list=PLID123")
    assert m is not None
    assert m.group(1) == "PLID123"

def test_trunc():
    assert strutils.trunc("hello world", 5) == "hell…"
    assert strutils.trunc("hi", 5) == "hi"

def test_cout():
    with patch('builtins.print') as mock_print:
        strutils.cout("hello", "world")
        mock_print.assert_called_once_with("hello", "world", flush=True, end="")

def test_prompt():
    with patch('builtins.input', return_value='y'):
        assert strutils.prompt("Do you agree?") == True
    with patch('builtins.input', return_value='n'):
        assert strutils.prompt("Do you agree?") == False
    with patch('builtins.input', side_effect=['', 'y']):
        assert strutils.prompt("Do you agree?", default='y') == True

def test_get_terminal_size():
    with patch('strutils.termios.tcgetwinsize', return_value=(24, 80)):
        assert strutils.get_terminal_size() == (24, 80)

@contextmanager
def mock_terminal(read_side_effect):
    with patch('strutils.os.get_terminal_size') as mock_gts, \
         patch('strutils.get_terminal_size', return_value=(80, 24)), \
         patch('strutils.get_cursor_position', return_value=(24, 80)), \
         patch('strutils.sys.stdin.read', side_effect=read_side_effect), \
         patch('strutils.sys.stdout.write'), \
         patch('strutils.termios.tcgetattr', return_value=[0,0,0,0,0,0,0]), \
         patch('strutils.termios.tcsetattr'), \
         patch('strutils.tty.setraw'), \
         patch('strutils.sys.stdin.fileno', return_value=0):
        mock_gts.return_value.lines = 24
        mock_gts.return_value.columns = 80
        yield

def test_radio_dial():
    with mock_terminal(read_side_effect=['\n']):
        assert strutils.radio_dial(["Opt A", "Opt B"]) == 0

    with mock_terminal(read_side_effect=['2', '\n']):
        assert strutils.radio_dial(["Opt A", "Opt B", "Opt C"]) == 1

    with mock_terminal(read_side_effect=['\x1b', '[', 'B', '\x1b', '[', 'B', '\n']):
        assert strutils.radio_dial(["Opt A", "Opt B", "Opt C"]) == 2

    with mock_terminal(read_side_effect=['5', '3']):
        assert strutils.radio_dial(["Opt A", "Opt B", "Opt C"]) == 2

def test_checklist_prompt_end_brings_to_submit():
    with mock_terminal(read_side_effect=['\x1b', '[', 'F', '\n']):
        res = strutils.checklist_prompt(["A", "B"], default=False)
        assert res == [False, False]

def test_checklist_prompt_navigation_and_selection():
    # Sequence: 
    # 1. Space (select A)
    # 2. Down (to B)
    # 3. Space (select B)
    # 4. Down (to C)
    # 5. Space (select C)
    # 6. Up (to B)
    # 7. Space (unselect B)
    # 8. Down, Down (to Accept)
    # 9. Enter
    sequence = [
        ' ', 
        '\x1b', '[', 'B', 
        ' ', 
        '\x1b', '[', 'B', 
        ' ', 
        '\x1b', '[', 'A', 
        ' ', 
        '\x1b', '[', 'B', '\x1b', '[', 'B', 
        '\n'
    ]
    with mock_terminal(read_side_effect=sequence):
        res = strutils.checklist_prompt(["A", "B", "C"], default=False)
        assert res == [True, False, True]

def test_input_list():
    with patch('builtins.input', side_effect=['item1', 'item2', '']), \
         patch('builtins.print'):
        assert strutils.input_list("Enter items:") == ['item1', 'item2']

def test_format_size():
    # Bytes: no decimal places
    assert strutils.format_size(0) == "0 B"
    assert strutils.format_size(512) == "512 B"
    assert strutils.format_size(999) == "999 B"

    # 1000 B crosses into KB (still divided by 1024)
    assert strutils.format_size(1000) == "0.98 KB"
    assert strutils.format_size(1024) == "1.00 KB"
    assert strutils.format_size(1536) == "1.50 KB"

    # 1000 KB crosses into MB
    assert strutils.format_size(1000 * 1024) == "0.98 MB"
    assert strutils.format_size(1024 ** 2) == "1.00 MB"
    assert strutils.format_size(2.5 * 1024 ** 2) == "2.50 MB"

    # Gigabytes
    assert strutils.format_size(1024 ** 3) == "1.00 GB"

    # Terabytes
    assert strutils.format_size(1024 ** 4) == "1.00 TB"

    # Petabytes — beyond TB the loop exits and the fallback PB line is used
    assert strutils.format_size(1024 ** 5) == "1.00 PB"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_md(tmp_path, content: str) -> Path:
    """Write *content* to a temp .md file and return the Path."""
    p = tmp_path / "test.md"
    p.write_text(content)
    return p

# ---------------------------------------------------------------------------
# write_frontmatter_key tests
# ---------------------------------------------------------------------------

def test_write_frontmatter_key_update_existing_list(tmp_path):
    """Overwrite an existing list key with new values."""
    md = _make_md(tmp_path, "---\ntags:\n  - \"old\"\ntitle: hello\n---\nbody\n")
    strutils.write_frontmatter_key(md, "tags", ["new1", "new2"])
    result = md.read_text()
    assert "  - \"new1\"" in result
    assert "  - \"new2\"" in result
    assert "old" not in result
    assert "title: hello" in result  # other keys preserved

def test_write_frontmatter_key_insert_new_list_default(tmp_path):
    """Insert a new key when insert_after_key is not specified (defaults to "---").

    With no insert_after_key the function uses "---" as the sentinel, which
    means insertafterkeyendsline is set to the *closing* "---" line.  The new
    key is therefore inserted just before that closing "---", i.e. after all
    existing keys.
    """
    md = _make_md(tmp_path, "---\ntitle: hello\n---\nbody\n")
    strutils.write_frontmatter_key(md, "tags", ["a", "b"])
    result = md.read_text()
    lines = result.split("\n")
    assert lines[0] == "---"
    # tags: must appear somewhere inside the frontmatter block
    closing = lines.index("---", 1)
    tags_idx = lines.index("tags:")
    assert 0 < tags_idx < closing
    assert "  - \"a\"" in result
    assert "  - \"b\"" in result
    assert "title: hello" in result

def test_write_frontmatter_key_insert_after_specific_key(tmp_path):
    """insert_after_key places the new key right after the named key."""
    md = _make_md(tmp_path, "---\ntitle: hello\nauthor: bob\n---\nbody\n")
    strutils.write_frontmatter_key(md, "tags", ["x"], insert_after_key="title")
    result = md.read_text()
    lines = result.split("\n")
    title_idx = lines.index("title: hello")
    tags_idx = lines.index("tags:")
    assert tags_idx == title_idx + 1

def test_write_frontmatter_key_remove_existing_key(tmp_path):
    """Passing a falsy non-list value removes the key from frontmatter.
    """
    md = _make_md(tmp_path, "---\ntags:\n  - \"old\"\ntitle: hello\n---\nbody\n")
    strutils.write_frontmatter_key(md, "tags", None)
    result = md.read_text()
    assert "tags:" not in result
    assert "old" not in result
    assert "title: hello" in result

def test_write_frontmatter_key_remove_nonexistent_key_is_noop(tmp_path):
    """Passing a falsy non-list value for a key that doesn't exist is a no-op."""
    original = "---\ntitle: hello\n---\nbody\n"
    md = _make_md(tmp_path, original)
    strutils.write_frontmatter_key(md, "tags", None)
    assert md.read_text() == original

def test_write_frontmatter_key_invalid_key_raises(tmp_path):
    """An invalid key name raises ValueError."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\n")
    import pytest
    with pytest.raises(ValueError, match="valid yaml key"):
        strutils.write_frontmatter_key(md, "Invalid Key!", ["v"])

def test_write_frontmatter_key_invalid_insert_after_key_raises(tmp_path):
    """An invalid insert_after_key raises ValueError."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\n")
    import pytest
    with pytest.raises(ValueError, match="valid yaml key"):
        strutils.write_frontmatter_key(md, "tags", ["v"], insert_after_key="Bad Key!")

def test_write_frontmatter_key_unknown_value_type_raises(tmp_path):
    """A non-list, non-string, non-falsy value (e.g. int) raises ValueError."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\n")
    import pytest
    with pytest.raises(ValueError, match="Unknown value type"):
        strutils.write_frontmatter_key(md, "tags", 42)

def test_write_frontmatter_key_list_with_quotes(tmp_path):
    """List values containing double-quotes are properly escaped."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\nbody\n")
    strutils.write_frontmatter_key(md, "tags", ['say "hi"'])
    result = md.read_text()
    assert '  - "say \\"hi\\""' in result

def test_write_frontmatter_key_insert_new_string(tmp_path):
    """Insert a brand-new string key into the frontmatter."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\nbody\n")
    strutils.write_frontmatter_key(md, "source", "https://example.com")
    result = md.read_text()
    assert 'source: "https://example.com"' in result
    assert "title: hello" in result

def test_write_frontmatter_key_update_existing_string(tmp_path):
    """Overwrite an existing single-line string key."""
    md = _make_md(tmp_path, '---\nsource: "old-url"\ntitle: hello\n---\nbody\n')
    strutils.write_frontmatter_key(md, "source", "new-url")
    result = md.read_text()
    assert 'source: "new-url"' in result
    assert "old-url" not in result
    assert "title: hello" in result

def test_write_frontmatter_key_overwrite_list_with_string(tmp_path):
    """Replace a multi-line list key with a single string value."""
    md = _make_md(tmp_path, '---\ntags:\n  - "a"\n  - "b"\ntitle: hello\n---\nbody\n')
    strutils.write_frontmatter_key(md, "tags", "single")
    result = md.read_text()
    assert 'tags: "single"' in result
    assert '  - ' not in result
    assert "title: hello" in result

def test_write_frontmatter_key_string_with_quotes(tmp_path):
    """Double-quotes inside a string value are escaped."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\n")
    strutils.write_frontmatter_key(md, "source", 'say "hi"')
    result = md.read_text()
    assert 'source: "say \\"hi\\""' in result

def test_write_frontmatter_key_string_with_newline_raises(tmp_path):
    """A string value containing a newline raises ValueError."""
    md = _make_md(tmp_path, "---\ntitle: hello\n---\n")
    import pytest
    with pytest.raises(ValueError, match="newlines"):
        strutils.write_frontmatter_key(md, "source", "line1\nline2")
