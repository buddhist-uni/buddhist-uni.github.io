import sys
from unittest.mock import MagicMock, patch
import numpy as np

# We need to mock TagPredictor and yaspin before importing nearestpdf
# because it has top-level execution code that calls them.
sys.modules['yaspin'] = MagicMock()
with patch('tag_predictor.TagPredictor.load'), patch('yaspin.yaspin'):
    # Also mock titlematch before it can be imported inside functions
    sys.modules['titlematch'] = MagicMock()
    import nearestpdf

@patch('nearestpdf.tag_predictor')
@patch('nearestpdf.normalize_text')
@patch('joblib.dump')
def test_embed_needle(mock_joblib_dump, mock_normalize, mock_tag_predictor):
    mock_normalize.return_value = "stemmed text"
    
    # Mock joblib.dump to simulate enough compression size
    def side_effect(val, buf, **kwargs):
        buf.write(b'a' * 500) # > MIN_PICKLE_SIZE_TO_COMPARE (400)
    mock_joblib_dump.side_effect = side_effect
    
    mock_embedding = MagicMock()
    mock_embedding.nnz = 150 # > MIN_VOCAB_SIZE_TO_COMPARE (120)
    mock_tag_predictor.tfidf_vectorize_texts.return_value = [mock_embedding]
    
    res = nearestpdf.embed_needle("some text")
    assert res == mock_embedding
    mock_normalize.assert_called_once_with("some text")

@patch('nearestpdf.tag_predictor')
@patch('nearestpdf.normalize_text')
@patch('joblib.dump')
def test_embed_needle_too_small(mock_joblib_dump, mock_normalize, mock_tag_predictor):
    mock_normalize.return_value = "short"
    
    # Mock joblib.dump to simulate small compression size
    def side_effect(val, buf, **kwargs):
        buf.write(b'a' * 10) # < MIN_PICKLE_SIZE_TO_COMPARE (400)
    mock_joblib_dump.side_effect = side_effect
    
    res = nearestpdf.embed_needle("short")
    assert res is None

@patch('nearestpdf.embed_needle')
@patch('titlematch.probability_filename_matches')
@patch('nearestpdf.fast_cosine_similarity')
def test_find_matching_files(mock_fast_cos, mock_titlematch, mock_embed):
    # Setup global state
    nearestpdf.corpus_embeddings = np.array([[1, 0], [0, 1]])
    nearestpdf.google_files = [{'name': 'file1', 'id': 'id1'}, {'name': 'file2', 'id': 'id2'}]
    nearestpdf.picklefiles = [MagicMock(stem='id1'), MagicMock(stem='id2')]
    
    mock_embed.return_value = MagicMock()
    # titlematch.probability_filename_matches returns a list of scores
    mock_titlematch.return_value = [0.8, 0.1] # file1 matches title, file2 doesn't
    
    # fast_cosine_similarity will be called on the filtered embeddings
    # filtered_embeddings = corpus_embeddings[reasonable_indexes]
    # reasonable_indexes = np.where(all_title_sims > MIN_TITLE_SIM)[0] -> [0]
    mock_fast_cos.return_value = np.array([0.9])
    
    results = nearestpdf.find_matching_files("title", "author", "contents")
    
    assert len(results) > 0
    assert results[0][0]['id'] == 'id1'
    # Check p_value calculation (roughly)
    # z = (18 * 0.9) + (10 * 0.8) - 19 = 16.2 + 8 - 19 = 5.2
    # p = 1 / (1 + exp(5.2 / -3)) = 1 / (1 + exp(-1.733)) = 1 / (1 + 0.176) = 0.85
    assert 0.8 < results[0][1] < 0.9

@patch('nearestpdf.calculate_all_similarities_to_string')
def test_file_closest_to_string(mock_calc):
    nearestpdf.picklefiles = [MagicMock(stem='id1'), MagicMock(stem='id2')]
    mock_calc.return_value = np.array([0.5, 0.95])
    
    file_id, score = nearestpdf.file_closest_to_string("needle")
    assert file_id == 'id2'
    assert score == 0.95

@patch('nearestpdf.calculate_all_similarities_to_string')
def test_n_closest_files_to_string(mock_calc):
    nearestpdf.picklefiles = [MagicMock(stem='id1'), MagicMock(stem='id2'), MagicMock(stem='id3')]
    mock_calc.return_value = np.array([0.5, 0.95, 0.8])
    
    results = nearestpdf.n_closest_files_to_string("needle", 2)
    assert len(results) == 2
    assert results[0][0] == 'id2'
    assert results[1][0] == 'id3'

@patch('nearestpdf.calculate_all_similarities_to_string')
def test_all_files_within(mock_calc):
    nearestpdf.picklefiles = [MagicMock(stem='id1'), MagicMock(stem='id2'), MagicMock(stem='id3')]
    mock_calc.return_value = np.array([0.5, 0.95, 0.8])
    
    results = nearestpdf.all_files_within("needle", min_similarity=0.7)
    assert len(results) == 2
    assert results[0][0] == 'id2'
    assert results[1][0] == 'id3'

def test_find_close_pairs():
    sim_matrix = np.array([
        [0, 0.95, 0.5],
        [0, 0, 0.2],
        [0, 0, 0]
    ])
    pairs = nearestpdf.find_close_pairs(sim_matrix, min_similarity=0.9)
    assert len(pairs) == 1
    assert pairs[0] == (0, 1, 0.95)

@patch('nearestpdf._load_embeddings_for_pickles')
@patch('nearestpdf._load_filesizes')
@patch('nearestpdf.TagPredictor')
def test_load(mock_tag_predictor, mock_load_filesizes, mock_load_embeddings):
    # This test is a bit complex due to global variables and multiple mocks
    with patch('gdrive.gcache') as mock_gcache, \
         patch('train_tag_predictor.save_all_drive_texts') as mock_save, \
         patch('train_tag_predictor.NORMALIZED_TEXT_FOLDER') as mock_folder:
        
        mock_gcache.sql_query.return_value = [{'id': 'id1', 'size': 1000}, {'id': 'id2', 'size': 2000}]
        mock_gcache.get_item.side_effect = lambda x: {'id': x, 'size': 1000 if x == 'id1' else 2000}
    
        # We need objects that can be sorted. sorted() uses < ( __lt__ )
        mock_file1 = MagicMock(spec=['stem', 'stat', '__lt__'])
        mock_file1.stem = 'id1'
        mock_file1.stat.return_value.st_size = 1000
        mock_file1.__lt__.side_effect = lambda other: mock_file1.stem < other.stem
        
        mock_file2 = MagicMock(spec=['stem', 'stat', '__lt__'])
        mock_file2.stem = 'id2'
        mock_file2.stat.return_value.st_size = 1000
        mock_file2.__lt__.side_effect = lambda other: mock_file2.stem < other.stem
        
        mock_folder.glob.return_value = [mock_file2, mock_file1] # Out of order to test sorting
        
        # Mock embeddings - 2 rows
        mock_emb = MagicMock()
        mock_emb.indptr = np.array([0, 150, 300]) # row_nnzs = [150, 150]
        mock_emb.__getitem__.side_effect = lambda idx: mock_emb # Simple slice mock
        mock_emb.shape = (2, 100)
        mock_load_embeddings.return_value = mock_emb
        
        mock_load_filesizes.return_value = [500, 500] # small enough size ratio
        
        # Reset globals to ensure clean test
        nearestpdf.corpus_embeddings = None
        
        nearestpdf.load()
        
        assert nearestpdf.corpus_embeddings is not None
        assert len(nearestpdf.picklefiles) == 2
        assert nearestpdf.gid_to_idx['id1'] == 0
        assert nearestpdf.gid_to_idx['id2'] == 1

@patch('nearestpdf.embed_needle')
@patch('nearestpdf.fast_cosine_similarity')
def test_calculate_all_similarities_to_string(mock_fast_cos, mock_embed):
    nearestpdf.corpus_embeddings = MagicMock()
    mock_embed.return_value = MagicMock()
    mock_fast_cos.return_value = np.array([0.1, 0.2])
    
    res = nearestpdf.calculate_all_similarities_to_string("needle")
    assert np.allclose(res, [0.1, 0.2])

@patch('nearestpdf.prompt')
@patch('nearestpdf.tqdm_process_map')
@patch('joblib.dump')
def test_calculate_similarity_matrix(mock_joblib_dump, mock_tqdm, mock_prompt):
    mock_prompt.return_value = True
    # mock_tqdm returns a list of chunks. 
    # _calc_sim_chunk returns (chunk_size, N)
    mock_tqdm.return_value = [np.array([[0.5, 0.9], [0.8, 0.4]])]
    
    nearestpdf.corpus_embeddings = MagicMock()
    nearestpdf.corpus_embeddings.shape = (2, 10)
    
    res = nearestpdf.calculate_similarity_matrix()
    assert res.shape == (2, 2)
    assert res[0, 1] == 0.9
    assert res[0, 0] == 0 # diagonal zeroed
    assert res[1, 0] == 0 # upper triangular

def test_calc_sim_chunk():
    nearestpdf.corpus_embeddings = MagicMock()
    mock_slice = MagicMock()
    nearestpdf.corpus_embeddings.__getitem__.return_value = mock_slice
    
    mock_res = MagicMock()
    mock_res.toarray.return_value = np.array([[0.5, 0.9]])
    mock_slice.__matmul__.return_value = mock_res
    
    res = nearestpdf._calc_sim_chunk((0, 1))
    assert np.allclose(res, [[0.5, 0.9]])

@patch('nearestpdf.joblib.load')
@patch('nearestpdf.joblib.dump')
@patch('gdrive.FileDistinctionManager')
@patch('gdrive.is_duplicate_prompt')
@patch('gdrive.gcache.get_item')
def test_review_close_pairs(mock_get_item, mock_prompt, mock_distinction_manager, mock_joblib_dump, mock_joblib_load):
    # Setup mocks
    mock_dist = MagicMock()
    mock_distinction_manager.return_value = mock_dist
    mock_dist.are_distinct.return_value = False
    
    mock_prompt.return_value = "merge_a"
    
    # Mock files
    fa = {'id': 'id_a', 'parent_id': 'parent_1', 'name': 'File A'}
    fb = {'id': 'id_b', 'parent_id': 'parent_1', 'name': 'File B'}
    fc = {'id': 'id_c', 'parent_id': 'parent_1', 'name': 'File C'}
    
    nearestpdf.google_files = [fa, fb, fc]
    nearestpdf.DECISION_HISTORY_FILE = MagicMock()
    nearestpdf.DECISION_HISTORY_FILE.exists.return_value = False
    
    import gdrive
    gdrive.OLD_VERSIONS_FOLDER_ID = 'graveyard'
    
    # Define close pairs: (0, 1, 0.95) and (0, 2, 0.93)
    # i.e., (File A, File B) and (File A, File C)
    close_pairs = [(0, 1, 0.95), (0, 2, 0.93)]
    
    # Scenario: 
    # 1. First pair (A, B) is processed. 
    # 2. handle_close_pair_decision is called.
    # 3. For the second pair (A, C), gcache.get_item('id_a') is called.
    # 4. We simulate that File A was moved to the graveyard by returning it with a new parent.
    
    def side_effect_get_item(file_id):
        if file_id == 'id_a' and mock_prompt.called:
            return {'id': 'id_a', 'parent_id': 'graveyard', 'name': 'File A'}
        if file_id == 'id_a': return fa
        if file_id == 'id_b': return fb
        if file_id == 'id_c': return fc
        return None
    mock_get_item.side_effect = side_effect_get_item
    
    nearestpdf.review_close_pairs(close_pairs)
    
    # Should only prompt once because File A moved to graveyard
    assert mock_prompt.call_count == 1
    mock_dist.handle_close_pair_decision.assert_called_once()
    assert mock_joblib_dump.call_count == 1

@patch('nearestpdf.joblib.load')
@patch('nearestpdf.joblib.dump')
@patch('gdrive.FileDistinctionManager')
@patch('gdrive.is_duplicate_prompt')
@patch('gdrive.gcache.get_item')
def test_review_close_pairs_already_distinct(mock_get_item, mock_prompt, mock_distinction_manager, mock_joblib_dump, mock_joblib_load):
    # Setup mocks
    mock_dist = MagicMock()
    mock_distinction_manager.return_value = mock_dist
    
    # First pair (A, B) is NOT distinct yet
    # Second pair (A, C) IS distinct (maybe because A and C were marked distinct in the first step)
    def side_effect_are_distinct(id1, id2):
        if id1 == 'id_a' and id2 == 'id_c':
            return True
        return False
    mock_dist.are_distinct.side_effect = side_effect_are_distinct
    
    fa = {'id': 'id_a', 'parent_id': 'p1', 'name': 'A'}
    fb = {'id': 'id_b', 'parent_id': 'p1', 'name': 'B'}
    fc = {'id': 'id_c', 'parent_id': 'p1', 'name': 'C'}
    
    nearestpdf.google_files = [fa, fb, fc]
    nearestpdf.DECISION_HISTORY_FILE = MagicMock()
    nearestpdf.DECISION_HISTORY_FILE.exists.return_value = False
    
    mock_get_item.side_effect = lambda x: {'id': x, 'parent_id': 'p1'}
    
    close_pairs = [(0, 1, 0.95), (0, 2, 0.93)]
    
    nearestpdf.review_close_pairs(close_pairs)
    
    # Should skip the second pair because it's distinct
    assert mock_prompt.call_count == 1
