import gdrive_base

ID28 = "aBcDeFgHiJkLmNoPqRsTuVwXyZ12"        # 28 chars
ID33 = "1HyFuDPC2S3vZJU-KgEmQXNrO6R9Jl64m"  # 33 chars  ← the original bug case
ID44 = "aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789012345678"  # 44 chars
assert len(ID28) == 28
assert len(ID33) == 33
assert len(ID44) == 44

class TestLinkToId:
    def test_none_returns_none(self):
        assert gdrive_base.link_to_id(None) is None

    def test_empty_string_returns_none(self):
        assert gdrive_base.link_to_id("") is None

    def test_unrecognised_url_returns_none(self):
        assert gdrive_base.link_to_id("https://example.com/nothing") is None

    def test_short_random_string_returns_none(self):
        assert gdrive_base.link_to_id("notanid") is None

    def test_bare_28char_id(self):
        assert gdrive_base.link_to_id(ID28) == ID28

    def test_bare_33char_id(self):
        assert gdrive_base.link_to_id(ID33) == ID33

    def test_bare_44char_id(self):
        assert gdrive_base.link_to_id(ID44) == ID44

    def test_bare_id_too_short_returns_none(self):
        assert gdrive_base.link_to_id("short") is None

    def test_bare_id_wrong_length_returns_none(self):
        # 30 chars — not 28, 33, or 44
        assert gdrive_base.link_to_id("a" * 30) is None
    
    def test_document_edit_link(self):
        url = f"https://docs.google.com/document/d/{ID33}/edit?usp=drivesdk"
        assert gdrive_base.link_to_id(url) == ID33

    def test_spreadsheet_link(self):
        url = f"https://docs.google.com/spreadsheets/d/{ID33}/edit"
        assert gdrive_base.link_to_id(url) == ID33

    def test_presentation_link(self):
        url = f"https://docs.google.com/presentation/d/{ID28}/edit"
        assert gdrive_base.link_to_id(url) == ID28

    def test_forms_link(self):
        url = f"https://docs.google.com/forms/d/{ID44}/edit"
        assert gdrive_base.link_to_id(url) == ID44

    def test_document_view_link_no_trailing_slash(self):
        url = f"https://docs.google.com/document/d/{ID33}"
        assert gdrive_base.link_to_id(url) == ID33

    def test_drivesdk_33char_regression(self):
        """The original bug: 33-char ID with usp=drivesdk was losing last 5 chars."""
        url = f"https://drive.google.com/file/d/{ID33}/view?usp=drivesdk"
        result = gdrive_base.link_to_id(url)
        assert result == ID33, f"Expected {ID33!r}, got {result!r}"

    def test_drivesdk_28char(self):
        url = f"https://drive.google.com/file/d/{ID28}/view?usp=drivesdk"
        assert gdrive_base.link_to_id(url) == ID28

    def test_drivesdk_44char(self):
        url = f"https://drive.google.com/file/d/{ID44}/view?usp=drivesdk"
        assert gdrive_base.link_to_id(url) == ID44

    def test_sharing_usp(self):
        url = f"https://drive.google.com/file/d/{ID33}/view?usp=sharing"
        assert gdrive_base.link_to_id(url) == ID33

    def test_drive_link_usp(self):
        url = f"https://drive.google.com/file/d/{ID33}/view?usp=drive_link"
        assert gdrive_base.link_to_id(url) == ID33

    def test_share_link_usp(self):
        url = f"https://drive.google.com/file/d/{ID33}/view?usp=share_link"
        assert gdrive_base.link_to_id(url) == ID33

    def test_edit_action(self):
        url = f"https://drive.google.com/file/d/{ID33}/edit"
        assert gdrive_base.link_to_id(url) == ID33

    def test_no_action_no_usp(self):
        url = f"https://drive.google.com/file/d/{ID33}"
        assert gdrive_base.link_to_id(url) == ID33

    def test_drive_link_template(self):
        """Matches the DRIVE_LINK format string used elsewhere in gdrive_base."""
        url = gdrive_base.DRIVE_LINK.format(ID33)
        assert gdrive_base.link_to_id(url) == ID33

    def test_folder_link(self):
        url = f"https://drive.google.com/drive/folders/{ID33}"
        assert gdrive_base.link_to_id(url) == ID33

    def test_folder_link_with_query(self):
        url = f"https://drive.google.com/drive/folders/{ID33}?usp=sharing"
        assert gdrive_base.link_to_id(url) == ID33

    def test_folderview_link(self):
        url = f"https://drive.google.com/folderview?id={ID28}"
        assert gdrive_base.link_to_id(url) == ID28

    def test_open_id_link(self):
        url = f"https://drive.google.com/open?id={ID33}"
        assert gdrive_base.link_to_id(url) == ID33

    def test_open_id_link_with_extra_params(self):
        url = f"https://drive.google.com/open?id={ID33}&usp=sharing"
        assert gdrive_base.link_to_id(url) == ID33

class TestFolderLinkToId:
    def test_none_returns_none(self):
        assert gdrive_base.folderlink_to_id(None) is None

    def test_empty_returns_none(self):
        assert gdrive_base.folderlink_to_id("") is None

    def test_non_folder_link_returns_none(self):
        assert gdrive_base.folderlink_to_id("https://example.com") is None

    def test_plain_folder_link(self):
        url = f"https://drive.google.com/drive/folders/{ID33}"
        assert gdrive_base.folderlink_to_id(url) == ID33

    def test_folder_link_with_query_params(self):
        url = f"https://drive.google.com/drive/folders/{ID33}?usp=sharing"
        assert gdrive_base.folderlink_to_id(url) == ID33

    def test_folder_link_with_trailing_slash(self):
        url = f"https://drive.google.com/drive/folders/{ID33}/"
        assert gdrive_base.folderlink_to_id(url) == ID33

    def test_folderview_link(self):
        url = f"https://drive.google.com/folderview?id={ID28}"
        assert gdrive_base.folderlink_to_id(url) == ID28

    def test_folderview_link_with_extra_params(self):
        url = f"https://drive.google.com/folderview?id={ID28}&usp=sharing"
        assert gdrive_base.folderlink_to_id(url) == ID28

    def test_file_link_returns_none(self):
        """A /file/d/ link is NOT a folder link."""
        url = f"https://drive.google.com/file/d/{ID33}/view?usp=drivesdk"
        assert gdrive_base.folderlink_to_id(url) is None
