import sqlite3
from release_info import build_information, dataset_version, ai_configuration, DATASET_VERSION

def test_source_identity_and_credentials_are_safe(monkeypatch):
    monkeypatch.setenv('PV_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'private-test-value')
    result = ai_configuration()
    assert 'private-test-value' not in str(result)
    assert result['Credentials'] == 'Configured (not validated)'
    monkeypatch.delenv('GEMINI_API_KEY')
    assert result['Provider'] == 'gemini'
    assert ai_configuration()['Credentials'] == 'Missing GEMINI_API_KEY'
    assert len(build_information()['Source build']) == 16

def test_legacy_records_are_not_relabelled(tmp_path):
    path = str(tmp_path / 'legacy.db')
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE user_records (value TEXT)')
        conn.execute("INSERT INTO user_records VALUES ('preserve')")
    assert dataset_version(path) == 'Legacy / unversioned'
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT value FROM user_records').fetchone()[0] == 'preserve'

def test_current_demo_is_separate_and_recoverable(tmp_path, monkeypatch):
    import workspace
    monkeypatch.setattr(workspace, 'DATA_ROOT', tmp_path)
    token, old = workspace.open_workspace()
    _, new = workspace.open_workspace()
    assert old != new
    assert dataset_version(new) == DATASET_VERSION
    assert workspace.open_workspace(token)[1] == old
