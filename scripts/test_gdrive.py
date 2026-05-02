import pytest
from unittest import mock
import copy

import sys
from pathlib import Path
import gdrive

@pytest.fixture
def mock_website_config():
    with mock.patch('website.config', {
        'collections': {
            'tags': {
                'order': ['tag1.md', 'tag2.md']
            }
        }
    }):
        yield

@pytest.fixture
def mock_permissions():
    def _mock(ids, fields=None, public_ids=None):
        # Closure to capture public_ids if we want to customize it per call
        # but for simple mocking we'll just return private by default
        return [
            {
                'id': fid,
                'permissions': []
            }
            for fid in ids
        ]
    with mock.patch('gdrive.batch_get_files_by_id') as m:
        m.side_effect = _mock
        yield m

@pytest.fixture
def test_db(tmp_path):
    from local_gdrive import DriveCache
    db_path = tmp_path / "test_drive.sqlite"
    cache = DriveCache(db_path)
    # Add a user to satisfy references if any
    with cache._lock:
        cache.cursor.execute("INSERT INTO users (id, display_name, email) VALUES (1, 'Me', 'me@example.com')")
        cache.conn.commit()
    yield cache
    cache.close()

def test_select_ids_to_keep_same_slug_returns_both(mock_website_config, mock_permissions):
    """Two files in the *same* important slug folder.

    Old (loop) implementation:
      important_slugs = ['tag1', 'tag1']  => len == 2, condition never fires
      => falls through to later heuristics, NOT TAG_FOLDER

    New (set) implementation:
      unique_slugs = {'tag1'}  => len == 1, condition fires
      => returns both ids with reason TAG_FOLDER
    """
    files = [
        {'id': '1', 'parents': ['f1']},
        {'id': '2', 'parents': ['f1']},  # same folder → same slug
    ]
    folder_slugs = {'f1': 'tag1'}

    ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
    assert set(ids) == {'1', '2'}
    assert reason == gdrive.IDSelectionReason.TAG_FOLDER

def test_select_ids_to_keep_tag_folder(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'parents': ['f1']},
        {'id': '2', 'parents': ['f2']}
    ]
    folder_slugs = {'f1': 'tag1'} # slugged
    # f2 is not slugged
    
    ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
    assert ids == ['1']
    assert reason == gdrive.IDSelectionReason.TAG_FOLDER

def test_select_ids_to_keep_public(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'parents': ['f1']},
        {'id': '2', 'parents': ['f2']}
    ]
    folder_slugs = {}
    
    # Mock permissions to make '2' public
    mock_permissions.side_effect = lambda ids, fields: [
        {'id': '1', 'permissions': []},
        {'id': '2', 'permissions': [{'type': 'anyone'}]}
    ]
    
    ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
    assert ids == ['2']
    assert reason == gdrive.IDSelectionReason.IS_PUBLIC

def test_select_ids_to_keep_generic_subfolder(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'parent_id': 'p1', 'parents': ['p1']},
        {'id': '2', 'parent_id': 'p2', 'parents': ['p2']}
    ]
    folder_slugs = {}
    
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.side_effect = lambda fid: {
            'p1': {'id': 'p1', 'name': 'unread stuff', 'parents': ['shared_parent']},
            'p2': {'id': 'p2', 'name': 'important stuff', 'parents': ['shared_parent']}
        }.get(fid)
        
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['2']
        assert reason == gdrive.IDSelectionReason.GENERIC_SUBFOLDER

def test_select_ids_to_keep_tag_priority(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'parents': ['f1'], 'parent_id': 'f1'},
        {'id': '2', 'parents': ['f2'], 'parent_id': 'f2'}
    ]
    # tag1 is higher priority than tag2 in mock_website_config
    folder_slugs = {'f1': 'tag1', 'f2': 'tag2'}
    
    # We need to make sure they aren't caught by the first "one is slugged" check
    # because BOTH are slugged.
    
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.side_effect = lambda fid: {'id': fid, 'name': fid, 'parents': ['root']}
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['1']
        assert reason == gdrive.IDSelectionReason.TAG_PRIORITY

def test_select_ids_to_keep_realistic(mock_website_config, mock_permissions):
    from local_gdrive import DriveCache
    fixture_db = Path(__file__).parent / "test_fixtures" / "drive.sqlite"
    if not fixture_db.exists():
        pytest.skip("Fixture DB not found")
        
    test_cache = DriveCache(fixture_db)

    with mock.patch('gdrive.gcache', test_cache):
        # 17VpttQypHvoBExKbm9AX48iGFnmORgkX is in "Unread"
        # 1i4O9RG7ug2WWNpMN44qj-P1m2tfzoUBP is in "Early Indian Schools of Buddhism"
        file1 = test_cache.get_item('17VpttQypHvoBExKbm9AX48iGFnmORgkX')
        file2 = test_cache.get_item('1i4O9RG7ug2WWNpMN44qj-P1m2tfzoUBP')
        assert file1 is not None
        assert file2 is not None
        files = [file1, file2]
        folder_slugs = gdrive.load_folder_slugs() # in a realistic test, load the actual folder slugs
        
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['1i4O9RG7ug2WWNpMN44qj-P1m2tfzoUBP']
        assert reason == gdrive.IDSelectionReason.TAG_FOLDER

        # 1bCq5KZ2UQGt81N2qWBvr8sx7WnO_k-HS is in "Unread (Sangha)"
        # 17Ky1unlqJA_IkdL0Hzqxo_l9gPxjnar- is in "Buddhism"
        file1 = test_cache.get_item('1bCq5KZ2UQGt81N2qWBvr8sx7WnO_k-HS')
        file2 = test_cache.get_item('17Ky1unlqJA_IkdL0Hzqxo_l9gPxjnar-')
        
        assert file1 is not None
        assert file2 is not None
        files = [file1, file2]
        
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['17Ky1unlqJA_IkdL0Hzqxo_l9gPxjnar-']
        assert reason == gdrive.IDSelectionReason.TAG_FOLDER

def test_select_ids_to_keep_name_length(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'name': 'short', 'parent_id': 'f1', 'parents': ['f1']},
        {'id': '2', 'name': 'much_longer_name', 'parent_id': 'f1', 'parents': ['f1']}
    ]
    folder_slugs = {}
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.return_value = {'id': 'f1', 'name': 'f1', 'parents': ['root'], 'parent_id': 'root'}
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['2']
        assert reason == gdrive.IDSelectionReason.NAME_LENGTH

def test_select_ids_to_keep_eldest(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'name': 'same', 'parent_id': 'f1', 'parents': ['f1'], 'modifiedTime': '2023-01-02T00:00:00Z'},
        {'id': '2', 'name': 'same', 'parent_id': 'f1', 'parents': ['f1'], 'modifiedTime': '2023-01-01T00:00:00Z'}
    ]
    folder_slugs = {}
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.return_value = {'id': 'f1', 'name': 'f1', 'parents': ['root'], 'parent_id': 'root'}
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['2']
        assert reason == gdrive.IDSelectionReason.ELDEST_FILE

def test_select_ids_keeps_deeper_folders(mock_website_config, mock_permissions):
    files = [
        {'id': '1', 'parent_id': 'f1', 'parents': ['f1']},
        {'id': '2', 'parent_id': 'f2', 'parents': ['f2']}
    ]
    # f1 is at depth 1 (root -> f1)
    # f2 is at depth 2 (root -> p2 -> f2)
    folder_slugs = {} # bypass the check for slugged folders
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.side_effect = lambda fid: {
            'f1': {'id': 'f1', 'name': 'f1', 'parent_id': 'root', 'parents': ['root']},
            'f2': {'id': 'f2', 'name': 'f2', 'parent_id': 'p2', 'parents': ['p2']},
            'p2': {'id': 'p2', 'name': 'p2', 'parent_id': 'root', 'parents': ['root']},
            'root': {'id': 'root', 'name': 'root', 'parent_id': None, 'parents': []}
        }.get(fid)
        
        ids, reason = gdrive.select_ids_to_keep(files, folder_slugs)
        assert ids == ['2']
        assert reason == gdrive.IDSelectionReason.FOLDER_DEPTH

def test_guess_link_title():
    with mock.patch('requests.get') as mock_get:
        mock_response = mock.Mock()
        mock_response.text = "<title>Test Title - YouTube</title>"
        mock_get.return_value = mock_response
        assert gdrive.guess_link_title("http://example.com") == "Test Title"

def test_make_link_doc_html():
    res = gdrive.make_link_doc_html("Some Title", "http://example.com")
    assert "<h1>Some Title</h1>" in res
    assert "<a href=\"http://example.com\">http://example.com</a>" in res

def test_process_duplicate_files():
    files = [
        {
            "id": "1",
            "name": "short",
            "parent_id": "f1",
            "parents": ["f1"],
            "modifiedTime": "2023-01-01T00:00:00Z"
        },
        {
            "id": "2",
            "name": "longer_name",
            "parent_id": "f1",
            "parents": ["f1"],
            "modifiedTime": "2023-01-01T00:00:00Z"
        }
    ]
    folder_slugs = {}
    
    with mock.patch('gdrive.gcache') as mock_gcache:
        mock_gcache.get_item.return_value = {"id": "f1", "name": "f1_name", "parent_id": None, "parents": ["root"]}
        mock_gcache.files_exactly_named.return_value = []
        
        with mock.patch('gdrive.batch_get_files_by_id') as mock_batch:
            mock_batch.return_value = [{"id": "1", "permissions": []}, {"id": "2", "permissions": []}]
            
            kept = gdrive.process_duplicate_files(copy.deepcopy(files), folder_slugs, verbose=False, dry_run=True)
            assert len(kept) == 1
            assert kept[0]["id"] == "2" # Longest name

@mock.patch('gdrive.local_gdrive.DriveCache')
def test_remote_file_for_local_file(mock_gcache):
    with mock.patch('gdrive.has_file_already') as mock_has_file:
        mock_has_file.return_value = []
        with mock.patch('gdrive.gcache') as local_cache:
            local_cache.upload_file.return_value = "new_id"
            local_cache.get_item.return_value = {"id": "new_id", "name": "uploaded"}
            
            remote = gdrive.remote_file_for_local_file(mock.Mock(name="test"), {})
            assert remote["id"] == "new_id"

def extract_to_test_db(file_ids: list[str]):
    from gdrive import gcache
    from local_gdrive import DriveCache
    
    fixture_dir = Path(__file__).parent / "test_fixtures"
    fixture_dir.mkdir(exist_ok=True)
    db_path = fixture_dir / "drive.sqlite"
    
    dest_cache = DriveCache(db_path)
    
    # Ensure User ID 1 exists and matches the real one (the 'me' user)
    real_me = gcache.get_user(1)
    if real_me:
        with dest_cache._lock:
            dest_cache.cursor.execute(
                "INSERT OR IGNORE INTO users (id, display_name, email) VALUES (?, ?, ?)", 
                (real_me['id'], real_me['display_name'], real_me['email'])
            )
            dest_cache.conn.commit()
    
    ids_to_process = set(file_ids)
    processed_ids = set()
    
    while ids_to_process:
        fid = ids_to_process.pop()
        if fid in processed_ids or not fid:
            continue
            
        # Try active first, then trash
        item = gcache.get_item(fid) or gcache.get_trashed_item(fid)
        
        if not item:
            print(f"Warning: Item {fid} not found in gcache")
            continue
            
        item['trashed'] = False # Always keep as active in the test fixture
        print(f"Extracting {item['name']} ({fid})")
        dest_cache.upsert_item(item)
        processed_ids.add(fid)
        
        # Add parent to queue
        parent_id = item.get('parent_id')
        if parent_id and parent_id not in processed_ids:
            assert len(parent_id) in [19, 33], f"Unexpected parent ID length: {parent_id} ({len(parent_id)})"
            if len(parent_id) == 33:
                ids_to_process.add(parent_id)
            
    dest_cache.close()
    print(f"Done! Test fixture updated at {db_path}")

def test_file_distinction_manager_mark_distinct(test_db):
    from gdrive import FileDistinctionManager
    
    # Mock gdrive_base.write_property to avoid network calls
    with mock.patch('gdrive_base.write_property') as mock_write_property:
        # Upsert some dummy files with valid-length IDs (28 chars)
        ids = ['id_aaaaaaaaaaaaaaaaaaaaaaaaa', 'id_bbbbbbbbbbbbbbbbbbbbbbbbb']
        for fid in ids:
            test_db.upsert_item({
                'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
                'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
            })
        
        fdm = FileDistinctionManager(test_db)
        fdm.mark_distinct(ids[0], ids[1])
        
        assert fdm.are_distinct(ids[0], ids[1])
        assert fdm.are_distinct(ids[1], ids[0])
        
        # Verify database state
        with test_db._lock:
            test_db.cursor.execute("SELECT value FROM item_properties WHERE file_id = ? AND key = 'distinctFrom'", (ids[0],))
            assert test_db.cursor.fetchone()['value'] == ids[1]
            test_db.cursor.execute("SELECT value FROM item_properties WHERE file_id = ? AND key = 'distinctFrom'", (ids[1],))
            assert test_db.cursor.fetchone()['value'] == ids[0]
        assert mock_write_property.call_count == 2

def test_file_distinction_manager_repair_missing_file(test_db):
    from gdrive import FileDistinctionManager
    
    # Setup a cycle: A -> B -> C -> A
    # But B is "missing" from drive_items (deleted/trashed)
    ids = [
        'id_aaaaaaaaaaaaaaaaaaaaaaaaa',
        'id_bbbbbbbbbbbbbbbbbbbbbbbbb',
        'id_ccccccccccccccccccccccccc'
    ]
    
    with mock.patch('gdrive_base.write_property'):
        # Only A and C are in the database as active items
        for fid in [ids[0], ids[2]]:
            test_db.upsert_item({
                'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
                'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
            })
        
        # Manually inject the cycle properties
        # A points to B, C points to A
        with test_db._lock:
            test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[0], ids[1]))
            test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[2], ids[0]))
            test_db.conn.commit()
        
        # Initializing fdm should trigger _fix_pointers.
        fdm = FileDistinctionManager(test_db)
        
        # After repair, A should point to C and C should point to A
        assert fdm.are_distinct(ids[0], ids[2])
        assert ids[1] not in fdm.fileid_to_distinct_neighbors
        
        with test_db._lock:
            test_db.cursor.execute("SELECT value FROM item_properties WHERE file_id = ? AND key = 'distinctFrom'", (ids[0],))
            assert test_db.cursor.fetchone()['value'] == ids[2]
            test_db.cursor.execute("SELECT value FROM item_properties WHERE file_id = ? AND key = 'distinctFrom'", (ids[2],))
            assert test_db.cursor.fetchone()['value'] == ids[0]

def test_file_distinction_manager_add_to_cluster(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision
    
    ids = [
        'id_aaaaaaaaaaaaaaaaaaaaaaaaa',
        'id_bbbbbbbbbbbbbbbbbbbbbbbbb',
        'id_ccccccccccccccccccccccccc'
    ]
    with mock.patch('gdrive_base.write_property') as mock_write_property:
        with mock.patch('gdrive.is_duplicate_prompt', return_value=ClosePairDecision.THEY_ARE_DISTINCT):
            # Upsert A, B, C
            for fid in ids:
                test_db.upsert_item({
                    'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
                    'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
                })
            
            fdm = FileDistinctionManager(test_db)
            fdm.mark_distinct(ids[0], ids[1]) # A <-> B
            assert mock_write_property.call_count == 2
            fdm.mark_distinct(ids[2], ids[0]) # C + {A, B}
            assert mock_write_property.call_count == 4
            
            assert fdm.are_distinct(ids[0], ids[1])
            assert fdm.are_distinct(ids[1], ids[2])
            assert fdm.are_distinct(ids[2], ids[0])

def test_file_distinction_manager_merge_clusters(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision
    
    with mock.patch('gdrive_base.write_property'):
        with mock.patch('gdrive.is_duplicate_prompt', return_value=ClosePairDecision.THEY_ARE_DISTINCT):
            # Clusters: {1, 2, 3} and {4, 5, 6}
            ids = [f'id_{i}' + '1' * 24 for i in range(1, 7)]
            for fid in ids:
                test_db.upsert_item({
                    'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
                    'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
                })
            
            fdm = FileDistinctionManager(test_db)
            # Create Cluster 1: {id_1, id_2, id_3}
            fdm.mark_distinct(ids[0], ids[1])
            fdm.mark_distinct(ids[1], ids[2])
            
            # Create Cluster 2: {id_4, id_5, id_6}
            fdm.mark_distinct(ids[3], ids[4])
            fdm.mark_distinct(ids[4], ids[5])
            
            # Merge clusters by marking id_1 and id_4 as distinct
            fdm.mark_distinct(ids[0], ids[3])
            
            # Delete old manager and construct a new one from the test_db to verify persistence
            del fdm
            fdm = FileDistinctionManager(test_db)
            
            # All 6 IDs should now be distinct from each other
            for i in range(6):
                for j in range(6):
                    if i != j:
                        assert fdm.are_distinct(ids[i], ids[j]), f"IDs {ids[i]} and {ids[j]} should be distinct"

def test_file_distinction_manager_clear_distinctions(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision
    
    ids = [
        'id_aaaaaaaaaaaaaaaaaaaaaaaaa',
        'id_bbbbbbbbbbbbbbbbbbbbbbbbb',
        'id_ccccccccccccccccccccccccc'
    ]
    with mock.patch('gdrive_base.write_property'):
        for fid in ids:
            test_db.upsert_item({
                'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
                'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
            })
        
        fdm = FileDistinctionManager(test_db)
        with mock.patch('gdrive.is_duplicate_prompt', return_value=ClosePairDecision.THEY_ARE_DISTINCT):
            fdm.mark_distinct(ids[0], ids[1]) # A <-> B
            fdm.mark_distinct(ids[1], ids[2]) # A -> B -> C -> A
            
        assert fdm.are_distinct(ids[0], ids[1])
        assert fdm.are_distinct(ids[1], ids[2])
        assert fdm.are_distinct(ids[2], ids[0])
        
        # Now clear distinctions from B
        fdm.clear_distinctions_from(ids[1])
        
        assert not fdm.are_distinct(ids[0], ids[1])
        assert not fdm.are_distinct(ids[1], ids[2])
        assert fdm.are_distinct(ids[0], ids[2])
        assert fdm.are_distinct(ids[2], ids[0])

def test_handle_close_pair_decision_distinct(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision
    fdm = FileDistinctionManager(test_db)
    file_a = {'id': 'id_a' + '1' * 24}
    file_b = {'id': 'id_b' + '1' * 24}
    
    with mock.patch.object(fdm, 'mark_distinct') as mock_mark:
        fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_DISTINCT, file_a, file_b)
        mock_mark.assert_called_once_with(file_b['id'], file_a['id'])

def test_handle_close_pair_decision_same_simple(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision, IDSelectionReason
    fdm = FileDistinctionManager(test_db)
    file_a = {'id': 'id_a' + '1' * 24, 'name': 'file_a_with_a_longer_name', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    file_b = {'id': 'id_b' + '1' * 24, 'name': 'file_b', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    
    with mock.patch('gdrive.select_ids_to_keep', return_value=([file_a['id']], IDSelectionReason.NAME_LENGTH)):
        with mock.patch('gdrive.move_gfile') as mock_move:
            with mock.patch('gdrive.prompt', return_value=False):
                fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_THE_SAME, file_a, file_b)
                # Should keep A, move B to old versions
                mock_move.assert_called_once()
                args, _ = mock_move.call_args
                assert args[0] == file_b['id']

def test_handle_close_pair_decision_same_public_manual(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision, IDSelectionReason
    fdm = FileDistinctionManager(test_db)
    file_a = {'id': 'id_a' + '1' * 24, 'name': 'file_a', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    file_b = {'id': 'id_b' + '1' * 24, 'name': 'file_b', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    
    # Both public
    with mock.patch('gdrive.select_ids_to_keep', return_value=([file_a['id'], file_b['id']], IDSelectionReason.IS_PUBLIC)):
        with mock.patch('gdrive.radio_dial', return_value=1) as mock_radio: # User selects B to keep (A is old)
            with mock.patch('gdrive.move_gfile') as mock_move:
                with mock.patch('gdrive.prompt', return_value=False):
                    fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_THE_SAME, file_a, file_b)
                    # Should keep B, move A
                    mock_move.assert_called_once()
                    args, _ = mock_move.call_args
                    assert args[0] == file_a['id']

def test_handle_close_pair_decision_swap_distinction(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision, IDSelectionReason
    
    ids = ['id_a' + '1' * 24, 'id_b' + '1' * 24, 'id_c' + '1' * 24]
    # Cluster: A -> C -> A (B is new/duplicate of A)
    for fid in [ids[0], ids[2]]:
        test_db.upsert_item({
            'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
            'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
        })
    with test_db._lock:
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[0], ids[2]))
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[2], ids[0]))
        test_db.conn.commit()
        
    fdm = FileDistinctionManager(test_db)
    assert fdm.are_distinct(ids[0], ids[2])
    
    file_a = test_db.get_item(ids[0])
    file_a['properties'] = {'distinctFrom': ids[2]}
    file_b = {'id': ids[1], 'name': 'file_b', 'parents': ['root'], 'parent_id': 'root', 'properties': {}}
    
    # Decision: A is old, keep B.
    # Expected: B should now be distinct from C. A should have no distinctions.
    with mock.patch('gdrive.select_ids_to_keep', return_value=([ids[1]], IDSelectionReason.NAME_LENGTH)):
        with mock.patch('gdrive.move_gfile'):
            with mock.patch('gdrive.prompt', return_value=False):
                with mock.patch('gdrive_base.write_property'):
                    fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_THE_SAME, file_a, file_b)
                    
                    assert fdm.are_distinct(ids[1], ids[2])
                    assert not fdm.are_distinct(ids[0], ids[2])
                    assert ids[0] not in fdm.fileid_to_distinct_neighbors

def test_handle_close_pair_decision_merge_distinction(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision, IDSelectionReason
    
    # Cluster 1: A -> C -> A
    # Cluster 2: B -> D -> B
    # Decision: A is same as B, keep B.
    # Expected: Merge clusters into B -> D -> C -> B (A removed)
    ids = [f'id_{c}' + '1' * 24 for c in ['a', 'b', 'c', 'd']]
    for fid in ids:
        test_db.upsert_item({
            'id': fid, 'version': 1, 'name': fid, 'mimeType': 'text/plain',
            'parents': ['root'], 'modifiedTime': '2023-01-01T00:00:00Z', 'trashed': False, 'owner': 1
        })
    
    with test_db._lock:
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[0], ids[2]))
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[2], ids[0]))
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[1], ids[3]))
        test_db.cursor.execute("INSERT INTO item_properties (file_id, key, value) VALUES (?, 'distinctFrom', ?)", (ids[3], ids[1]))
        test_db.conn.commit()
        
    fdm = FileDistinctionManager(test_db)
    
    file_a = test_db.get_item(ids[0])
    file_a['properties'] = {'distinctFrom': ids[2]}
    file_b = test_db.get_item(ids[1])
    file_b['properties'] = {'distinctFrom': ids[3]}
    
    with mock.patch('gdrive.select_ids_to_keep', return_value=([ids[1]], IDSelectionReason.NAME_LENGTH)):
        with mock.patch('gdrive.move_gfile'):
            with mock.patch('gdrive.prompt', return_value=False):
                with mock.patch('gdrive_base.write_property'):
                    fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_THE_SAME, file_a, file_b)
                    
                    # All of {B, C, D} should be distinct from each other
                    for i in [1, 2, 3]:
                        for j in [1, 2, 3]:
                            if i != j:
                                assert fdm.are_distinct(ids[i], ids[j])
                    # A should be out
                    assert ids[0] not in fdm.fileid_to_distinct_neighbors

def test_handle_close_pair_decision_same_tag_folder(test_db):
    from gdrive import FileDistinctionManager, ClosePairDecision, IDSelectionReason
    fdm = FileDistinctionManager(test_db)
    file_a = {'id': 'id_a' + '1' * 24, 'name': 'file_a', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    file_b = {'id': 'id_b' + '1' * 24, 'name': 'file_b', 'parents': ['p1'], 'parent_id': 'p1', 'properties': {}}
    
    # Both in same tag folder
    with mock.patch('gdrive.select_ids_to_keep', return_value=([file_a['id'], file_b['id']], IDSelectionReason.TAG_FOLDER)):
        with mock.patch('gdrive.radio_dial', return_value=0): # User selects A to keep
            with mock.patch('gdrive.move_gfile') as mock_move:
                with mock.patch('gdrive.prompt', return_value=False):
                    fdm.handle_close_pair_decision(ClosePairDecision.THEY_ARE_THE_SAME, file_a, file_b)
                    mock_move.assert_called_once()
                    args, _ = mock_move.call_args
                    assert args[0] == file_b['id']

def test_get_course_suggestions_top_level():
    mock_folders = {
        'course1': {'public': 'link1', 'private': 'link2'},
        'course2': {'public': 'link3', 'private': 'link4'},
    }
    with mock.patch('gdrive.FOLDERS_DATA', return_value=mock_folders):
        suggestions = gdrive.get_course_suggestions('course')
        assert set(suggestions) == {'course1', 'course2'}
        
        suggestions = gdrive.get_course_suggestions('course1')
        assert suggestions == ['course1']

def test_get_course_suggestions_subfolders(test_db):
    mock_folders = {
        'course1': {'public': 'pub1', 'private': 'priv1'},
    }
    
    # Mock folderlink_to_id
    with mock.patch('gdrive.folderlink_to_id', return_value='priv1_id'), \
         mock.patch('gdrive.FOLDERS_DATA', return_value=mock_folders), \
         mock.patch('gdrive.gcache', test_db):
        
        # Inject items into test_db
        with test_db._lock:
            sql = "INSERT INTO drive_items (id, version, name, mime_type, parent_id, modified_time, owner) VALUES (?, ?, ?, ?, ?, ?, 1)"
            now = '2024-01-01T00:00:00Z'
            test_db.cursor.execute(sql, ('priv1_id', 1, 'Course 1', 'application/vnd.google-apps.folder', 'root', now))
            test_db.cursor.execute(sql, ('sub1_id', 1, 'Sub Folder 1', 'application/vnd.google-apps.folder', 'priv1_id', now))
            test_db.cursor.execute(sql, ('sub2_id', 1, 'Another Sub', 'application/vnd.google-apps.folder', 'priv1_id', now))
            test_db.cursor.execute(sql, ('subsub1_id', 1, 'Nested One', 'application/vnd.google-apps.folder', 'sub1_id', now))
            test_db.conn.commit()

        # course1/ -> matches subfolders of priv1_id
        suggestions = gdrive.get_course_suggestions('course1/')
        assert 'course1/Sub Folder 1/' in suggestions
        assert 'course1/Another Sub' in suggestions

        # course1/sub -> matches Sub Folder 1 (Another Sub doesn't contain "sub")
        # Wait, q in f['name'].lower()
        # "Sub Folder 1" contains "sub"
        # "Another Sub" contains "sub"
        suggestions = gdrive.get_course_suggestions('course1/sub')
        assert set(suggestions) == {'course1/Sub Folder 1/', 'course1/Another Sub'}
        
        # course1/Sub Folder 1/n -> matches Nested One
        suggestions = gdrive.get_course_suggestions('course1/Sub Folder 1/n')
        assert suggestions == ['course1/Sub Folder 1/Nested One']

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "extract":
        extract_to_test_db(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "extract":
        print("Usage: python scripts/test_gdrive.py extract <id1> <id2> ...")
