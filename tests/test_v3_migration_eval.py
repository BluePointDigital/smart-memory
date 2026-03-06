from __future__ import annotations

from cognitive_memory_system import CognitiveMemorySystem
from migration.v3_migration import V3Migration
from prompt_engine.schemas import SemanticMemory, MemorySource
from smart_memory_config import SmartMemoryV3Config, StorageConfig
from storage import JSONMemoryStore, SQLiteMemoryStore


def test_v3_migration_preserves_legacy_memory_and_backfills_fields(tmp_path):
    legacy_store = JSONMemoryStore(root=tmp_path / "legacy")
    legacy_memory = SemanticMemory(
        content="Smart Memory uses a local FastAPI server.",
        importance=0.8,
        source=MemorySource.CONVERSATION,
        entities=["smart memory"],
        schema_version="2.0",
    )
    legacy_store.save_memory(legacy_memory)

    migration = V3Migration(
        legacy_root=tmp_path / "legacy",
        sqlite_path=tmp_path / "v3" / "memory.sqlite",
    )
    report = migration.migrate()

    sqlite_store = SQLiteMemoryStore(tmp_path / "v3" / "memory.sqlite")
    migrated = sqlite_store.get_memory(legacy_memory.id)
    assert report.total_migrated == 1
    assert migrated is not None
    assert migrated.schema_version == "2.0"
    assert migrated.status.value == "active"
    assert migrated.lane_eligibility


def test_eval_runner_emits_all_modes(tmp_path):
    config = SmartMemoryV3Config(storage=StorageConfig(sqlite_path=str(tmp_path / "eval.sqlite"), json_root=str(tmp_path / "json")))
    system = CognitiveMemorySystem(config=config)
    reports = system.run_eval_case("preference_change")

    modes = {report.mode for report in reports}
    assert modes == {"baseline_v2", "v3_revision_only", "v3_full"}
    assert all(report.metrics.token_budget_compliant for report in reports)
