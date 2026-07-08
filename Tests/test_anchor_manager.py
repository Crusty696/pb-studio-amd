import json
from pathlib import Path
import numpy as np
import pytest
from pb_studio.pacing.anchor_manager import AnchorManager, AnchorData
from pb_studio.pacing.constants import AUDIO_FEATURE_DIM, EMBEDDING_DIM

def test_anchor_manager_atomic_save(tmp_path):
    # Setup AnchorManager with tmp_path as data directory
    manager = AnchorManager(project_id=123, data_dir=str(tmp_path))
    
    # Add an anchor
    audio_feat = np.ones(AUDIO_FEATURE_DIM, dtype=np.float32)
    video_emb = np.ones(EMBEDDING_DIM, dtype=np.float32)
    
    anchor_id = manager.add_anchor(
        audio_start=0.0,
        audio_end=2.0,
        video_path="test_video.mp4",
        audio_features=audio_feat,
        video_embedding=video_emb,
        label="test_label"
    )
    
    assert anchor_id is not None
    
    # Check that the file was created and is valid JSON
    anchor_file = tmp_path / "anchors_project_123.json"
    assert anchor_file.exists()
    
    with open(anchor_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["project_id"] == 123
    assert data["count"] == 1
    assert data["anchors"][0]["id"] == anchor_id
    assert data["anchors"][0]["label"] == "test_label"
    
    # Test atomic replacement by verifying load
    new_manager = AnchorManager(project_id=123, data_dir=str(tmp_path))
    assert new_manager.count == 1
    loaded_anchor = new_manager.get_all_anchors()[0]
    assert loaded_anchor.id == anchor_id
    assert loaded_anchor.label == "test_label"
