import pytest
import time
from pb_studio.core.vram_budget_manager import VRAMBudgetManager, ModelPriority

def test_vram_allocation_and_eviction():
    VRAMBudgetManager.reset_for_testing()
    mgr = VRAMBudgetManager(max_vram_mb=4096)
    
    # We should have exactly max - 500 (safety buffer)
    assert mgr.available_vram_mb == 4096 - 500
    
    # Register models
    mgr.register_model(
        "m1", "Model 1", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model(
        "m2", "Model 2", 1500, ModelPriority.MEDIUM,
        unload_callback=lambda: True,
    )
    mgr.register_model("m3", "Model 3", 2000, ModelPriority.HIGH)
    
    # Reserve and commit m1
    assert mgr.reserve("m1")
    assert mgr.commit("m1")
    assert mgr.is_model_loaded("m1")
    
    # Reserve and commit m2
    assert mgr.reserve("m2")
    assert mgr.commit("m2")
    assert mgr.is_model_loaded("m2")
    
    # VRAM should now be (4096 - 500) - 2500 = 1096
    assert mgr.available_vram_mb == 1096
    
    # Try to allocate m3 (needs 2000), should fail without force
    assert not mgr.reserve("m3", force=False)
    
    # Try to allocate m3 with force, should evict m1 (LOW)
    assert mgr.reserve("m3", force=True)
    assert not mgr.is_model_loaded("m1")
    assert mgr.is_model_loaded("m2")
    
    assert mgr.commit("m3")
    assert mgr.is_model_loaded("m3")

def test_eviction_lru():
    VRAMBudgetManager.reset_for_testing()
    mgr = VRAMBudgetManager(max_vram_mb=4096)
    
    mgr.register_model(
        "m1", "Model 1", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model(
        "m2", "Model 2", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model("m3", "Model 3", 2000, ModelPriority.LOW)
    
    assert mgr.reserve("m1")
    assert mgr.commit("m1")
    time.sleep(0.01) # Ensure time difference
    
    assert mgr.reserve("m2")
    assert mgr.commit("m2")
    
    # Both are LOW, but m1 is older. 
    # Available is (4096 - 500) - 2000 = 1596
    # We need 2000 for m3.
    assert mgr.reserve("m3", force=True)
    
    # m1 should be evicted because it's least recently used
    assert not mgr.is_model_loaded("m1")
    assert mgr.is_model_loaded("m2")
    assert mgr.commit("m3")
    assert mgr.is_model_loaded("m3")
