"""
Tests for the autocomplete RL (Thompson Sampling contextual bandit) system.
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vishwa.autocomplete.rl.strategies import (
    Strategy, STRATEGIES, STRATEGY_NAMES, get_strategy,
)
from vishwa.autocomplete.rl.features import (
    extract_language, extract_scope, extract_file_size,
    extract_position, extract_bucket_key,
)
from vishwa.autocomplete.rl.reward import compute_reward
from vishwa.autocomplete.rl.policy import (
    ThompsonSamplingPolicy, COLD_START_THRESHOLD, DECAY_INTERVAL,
    KILL_MIN_OBSERVATIONS, KILL_THRESHOLD,
)
from vishwa.autocomplete.rl.storage import PolicyStorage
from vishwa.autocomplete.context_builder import AutocompleteContext, FunctionInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_context(
    language="python",
    in_function=True,
    function_name="my_func",
    lines_before=None,
    lines_after=None,
    current_line="    x = 1",
    cursor_position=9,
    indent_level=1,
    file_path="test.py",
):
    """Create an AutocompleteContext with sensible defaults for testing."""
    if lines_before is None:
        lines_before = [f"    line{i}" for i in range(200)]
    if lines_after is None:
        lines_after = [f"    line_after{i}" for i in range(50)]
    return AutocompleteContext(
        file_path=file_path,
        language=language,
        current_line=current_line,
        lines_before=lines_before,
        lines_after=lines_after,
        cursor_position=cursor_position,
        in_function=in_function,
        function_name=function_name,
        indent_level=indent_level,
        imports=["import os", "import sys"],
        referenced_functions=[],
    )


# ===========================================================================
# Strategy tests
# ===========================================================================

class TestStrategies:
    def test_all_strategy_names_present(self):
        for name in STRATEGY_NAMES:
            assert name in STRATEGIES

    def test_get_strategy_valid(self):
        s = get_strategy("standard")
        assert s.name == "standard"
        assert s.lines_before == 15
        assert s.max_tokens == 100

    def test_get_strategy_invalid_raises(self):
        try:
            get_strategy("nonexistent")
            assert False, "Expected KeyError"
        except KeyError:
            pass

    def test_minimal_strategy_values(self):
        s = STRATEGIES["minimal"]
        assert s.lines_before == 5
        assert s.lines_after == 0
        assert s.include_imports is False
        assert s.include_functions is False
        assert s.max_tokens == 60

    def test_compact_strategy_values(self):
        s = STRATEGIES["compact"]
        assert s.lines_before == 10
        assert s.lines_after == 2
        assert s.include_imports is False
        assert s.max_tokens == 80

    def test_standard_strategy_values(self):
        s = STRATEGIES["standard"]
        assert s.lines_before == 15
        assert s.lines_after == 2
        assert s.include_imports is True
        assert s.max_imports == 10
        assert s.include_functions is True
        assert s.max_functions == 5
        assert s.max_tokens == 100

    def test_rich_strategy_values(self):
        s = STRATEGIES["rich"]
        assert s.lines_before == 20
        assert s.lines_after == 5
        assert s.max_imports == 15
        assert s.max_functions == 8
        assert s.max_tokens == 120

    def test_scope_aware_is_dynamic(self):
        s = STRATEGIES["scope_aware"]
        assert s.dynamic_scope is True
        assert s.max_scope_lines == 30
        assert s.lines_after == 3

    def test_strategies_are_frozen(self):
        s = STRATEGIES["minimal"]
        try:
            s.lines_before = 999
            assert False, "Expected FrozenInstanceError"
        except AttributeError:
            pass


# ===========================================================================
# Feature extraction tests
# ===========================================================================

class TestFeatureExtraction:
    def test_extract_language_python(self):
        ctx = make_context(language="python")
        assert extract_language(ctx) == "python"

    def test_extract_language_javascript(self):
        ctx = make_context(language="javascript")
        assert extract_language(ctx) == "javascript"

    def test_extract_language_typescript(self):
        ctx = make_context(language="typescript")
        assert extract_language(ctx) == "typescript"

    def test_extract_language_other(self):
        ctx = make_context(language="rust")
        assert extract_language(ctx) == "other"

    def test_extract_scope_function(self):
        ctx = make_context(in_function=True, function_name="my_func")
        assert extract_scope(ctx) == "function"

    def test_extract_scope_class(self):
        ctx = make_context(in_function=True, function_name="MyClass")
        assert extract_scope(ctx) == "class"

    def test_extract_scope_top_level(self):
        ctx = make_context(in_function=False, function_name=None)
        assert extract_scope(ctx) == "top_level"

    def test_extract_file_size_small(self):
        ctx = make_context(lines_before=["l"] * 30, lines_after=["l"] * 20)
        assert extract_file_size(ctx) == "small"  # 30 + 1 + 20 = 51 < 100

    def test_extract_file_size_medium(self):
        ctx = make_context(lines_before=["l"] * 200, lines_after=["l"] * 50)
        assert extract_file_size(ctx) == "medium"  # 200 + 1 + 50 = 251

    def test_extract_file_size_large(self):
        ctx = make_context(lines_before=["l"] * 400, lines_after=["l"] * 200)
        assert extract_file_size(ctx) == "large"  # 400 + 1 + 200 = 601

    def test_extract_position_start(self):
        # Previous line ends with ':', current line has more indent
        ctx = make_context(
            lines_before=["def foo():", "    "],
            current_line="        x = 1",
            lines_after=["        y = 2"],
            cursor_position=13,
        )
        # prev line "    " is blank, so check further
        # Let's use a clearer case:
        ctx = make_context(
            lines_before=["def foo():"],
            current_line="    x = 1",
            lines_after=["    y = 2"],
            cursor_position=9,
        )
        assert extract_position(ctx) == "start"

    def test_extract_position_mid(self):
        ctx = make_context(
            lines_before=["    x = 1", "    y = 2"],
            current_line="    z = 3",
            lines_after=["    w = 4"],
            cursor_position=9,
        )
        assert extract_position(ctx) == "mid"

    def test_extract_position_end(self):
        ctx = make_context(
            lines_before=["    x = 1"],
            current_line="    return x",
            lines_after=[""],
            cursor_position=12,
        )
        # Next line is empty, and the one after (if exists) could indicate end
        # With just one empty lines_after, it defaults to mid actually
        # Let's use a clearer case with dedent
        ctx = make_context(
            lines_before=["    x = 1"],
            current_line="    return x",
            lines_after=["def bar():"],
            cursor_position=12,
        )
        assert extract_position(ctx) == "end"

    def test_bucket_key_format(self):
        ctx = make_context(
            language="python",
            in_function=True,
            function_name="my_func",
            lines_before=["    l"] * 200,
            lines_after=["    l"] * 50,
        )
        key = extract_bucket_key(ctx)
        parts = key.split(":")
        assert len(parts) == 4
        assert parts[0] == "python"
        assert parts[1] == "function"
        assert parts[2] == "medium"
        assert parts[3] in ("start", "mid", "end")


# ===========================================================================
# Reward tests
# ===========================================================================

class TestReward:
    def test_accepted_fast(self):
        reward = compute_reward(accepted=True, latency_ms=0)
        assert abs(reward - 1.0) < 0.001

    def test_accepted_slow(self):
        reward = compute_reward(accepted=True, latency_ms=2000)
        assert abs(reward - 0.7) < 0.001

    def test_rejected_fast(self):
        reward = compute_reward(accepted=False, latency_ms=0)
        assert abs(reward - 0.3) < 0.001

    def test_rejected_slow(self):
        reward = compute_reward(accepted=False, latency_ms=2000)
        assert abs(reward - 0.0) < 0.001

    def test_rejected_very_slow(self):
        reward = compute_reward(accepted=False, latency_ms=5000)
        assert abs(reward - 0.0) < 0.001

    def test_accepted_mid_latency(self):
        reward = compute_reward(accepted=True, latency_ms=1000)
        expected = 0.7 + 0.3 * 0.5  # 0.85
        assert abs(reward - expected) < 0.001

    def test_reward_bounds(self):
        # Should always be in [0, 1]
        for accepted in [True, False]:
            for latency in [0, 100, 500, 1000, 2000, 5000]:
                r = compute_reward(accepted, latency)
                assert 0.0 <= r <= 1.0


# ===========================================================================
# Policy tests
# ===========================================================================

class TestThompsonSamplingPolicy:
    def test_cold_start_returns_standard(self):
        policy = ThompsonSamplingPolicy()
        for _ in range(COLD_START_THRESHOLD):
            assert policy.select_strategy("python:function:medium:mid") == "standard"

    def test_after_cold_start_can_select_others(self):
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = COLD_START_THRESHOLD  # past cold start

        # With default priors, standard has Beta(10,1) - very high
        # Run many selections to see if standard dominates (it should)
        selections = [policy.select_strategy("test_bucket") for _ in range(100)]
        # standard should appear most often due to strong prior
        standard_count = selections.count("standard")
        assert standard_count > 50  # Should be dominant

    def test_exploration_floor(self):
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = COLD_START_THRESHOLD

        # Run many trials, count non-standard selections
        # With 10% exploration, ~10% should be random
        with patch('vishwa.autocomplete.rl.policy.random') as mock_random:
            # Force exploration path
            mock_random.random.return_value = 0.05  # < 0.10 → exploration
            mock_random.choice.return_value = "minimal"
            result = policy.select_strategy("test_bucket")
            assert result == "minimal"

    def test_update_increments_params(self):
        policy = ThompsonSamplingPolicy()
        bucket = "python:function:medium:mid"

        # Get initial params for compact
        params_before = list(policy._get_params(bucket, "compact"))
        assert params_before == [1.0, 1.0]  # uninformed prior

        policy.update(bucket, "compact", 0.8)
        params_after = policy._get_params(bucket, "compact")
        assert abs(params_after[0] - 1.8) < 0.001  # alpha += 0.8
        assert abs(params_after[1] - 1.2) < 0.001  # beta += 0.2

    def test_decay_applied_at_interval(self):
        policy = ThompsonSamplingPolicy()
        bucket = "test_bucket"

        # Set up known params
        policy.buckets[bucket] = {"standard": [10.0, 2.0]}
        policy.total_interactions = DECAY_INTERVAL - 1

        # This update should trigger decay
        policy.update(bucket, "standard", 1.0)
        params = policy.buckets[bucket]["standard"]
        # After update: [11.0, 2.0], then decay: [11.0*0.95, 2.0*0.95]
        assert abs(params[0] - 11.0 * 0.95) < 0.001
        assert abs(params[1] - 2.0 * 0.95) < 0.001

    def test_kill_switch_disables_bad_strategy(self):
        policy = ThompsonSamplingPolicy()
        bucket = "test_bucket"

        # Set up a strategy with very low success rate
        # alpha=1, beta=60 → success_rate ≈ 0.016 < 0.05, total=61 > 50
        policy.buckets[bucket] = {"compact": [1.0, 60.0]}
        policy.total_interactions = 100  # past cold start

        # Trigger kill switch check
        policy._check_kill_switch(bucket, "compact")
        assert policy._is_disabled(bucket, "compact")

    def test_kill_switch_does_not_disable_standard(self):
        policy = ThompsonSamplingPolicy()
        bucket = "test_bucket"
        policy.buckets[bucket] = {"standard": [1.0, 60.0]}
        policy._check_kill_switch(bucket, "standard")
        assert not policy._is_disabled(bucket, "standard")

    def test_kill_switch_not_triggered_below_threshold(self):
        policy = ThompsonSamplingPolicy()
        bucket = "test_bucket"
        # Low observations
        policy.buckets[bucket] = {"compact": [1.0, 10.0]}
        policy._check_kill_switch(bucket, "compact")
        assert not policy._is_disabled(bucket, "compact")

    def test_disabled_strategy_excluded_from_selection(self):
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = COLD_START_THRESHOLD
        bucket = "test_bucket"

        # Disable all except standard
        for name in STRATEGY_NAMES:
            if name != "standard":
                if bucket not in policy.disabled_strategies:
                    policy.disabled_strategies[bucket] = []
                policy.disabled_strategies[bucket].append(name)

        # Should always pick standard since it's the only one available
        for _ in range(20):
            assert policy.select_strategy(bucket) == "standard"

    def test_get_stats(self):
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = 42
        policy.buckets["test"] = {"standard": [10.0, 2.0]}
        stats = policy.get_stats()
        assert stats["total_interactions"] == 42
        assert "test" in stats["buckets"]
        assert "standard" in stats["buckets"]["test"]
        assert stats["buckets"]["test"]["standard"]["alpha"] == 10.0


# ===========================================================================
# Storage tests
# ===========================================================================

class TestPolicyStorage:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.storage = PolicyStorage(policy_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_round_trip(self):
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = 150
        policy.buckets["py:fn:med:mid"] = {
            "standard": [15.0, 3.0],
            "compact": [5.0, 8.0],
        }
        policy.disabled_strategies["py:fn:med:mid"] = ["minimal"]

        self.storage.save(policy)

        # Load into fresh policy
        loaded = ThompsonSamplingPolicy()
        self.storage.load(loaded)

        assert loaded.total_interactions == 150
        assert loaded.buckets["py:fn:med:mid"]["standard"] == [15.0, 3.0]
        assert loaded.buckets["py:fn:med:mid"]["compact"] == [5.0, 8.0]
        assert loaded.disabled_strategies["py:fn:med:mid"] == ["minimal"]

    def test_load_nonexistent_file(self):
        policy = ThompsonSamplingPolicy()
        # Should not raise, just leave policy empty
        self.storage.load(policy)
        assert policy.total_interactions == 0
        assert policy.buckets == {}

    def test_save_creates_directory(self):
        nested_dir = self.tmpdir / "nested" / "deep"
        storage = PolicyStorage(policy_dir=nested_dir)
        policy = ThompsonSamplingPolicy()
        policy.total_interactions = 1
        storage.save(policy)
        assert (nested_dir / "autocomplete_policy.json").exists()

    def test_feedback_log(self):
        self.storage.log_feedback("py:fn:med:mid", "compact", True, 342.5)
        self.storage.log_feedback("py:fn:med:mid", "standard", False, 1200.0)

        feedback_file = self.tmpdir / "autocomplete_feedback.jsonl"
        assert feedback_file.exists()

        with open(feedback_file) as f:
            lines = f.readlines()
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["bucket"] == "py:fn:med:mid"
        assert entry1["strategy"] == "compact"
        assert entry1["accepted"] is True
        assert entry1["latency_ms"] == 342.5

        entry2 = json.loads(lines[1])
        assert entry2["accepted"] is False

    def test_feedback_log_truncation(self):
        # Write more than MAX entries
        from vishwa.autocomplete.rl.storage import MAX_FEEDBACK_ENTRIES

        for i in range(MAX_FEEDBACK_ENTRIES + 200):
            self.storage.log_feedback("bucket", "strategy", True, float(i))

        feedback_file = self.tmpdir / "autocomplete_feedback.jsonl"
        with open(feedback_file) as f:
            lines = f.readlines()
        assert len(lines) <= MAX_FEEDBACK_ENTRIES

    def test_incompatible_version_ignored(self):
        # Write a policy file with different version
        policy_file = self.tmpdir / "autocomplete_policy.json"
        self.tmpdir.mkdir(parents=True, exist_ok=True)
        with open(policy_file, "w") as f:
            json.dump({"version": 999, "total_interactions": 100}, f)

        policy = ThompsonSamplingPolicy()
        self.storage.load(policy)
        # Should be ignored due to version mismatch
        assert policy.total_interactions == 0


# ===========================================================================
# Integration tests
# ===========================================================================

class TestIntegration:
    """End-to-end test: context → features → policy → strategy → feedback → update."""

    def test_full_flow(self):
        # 1. Create context
        ctx = make_context(
            language="python",
            in_function=True,
            function_name="process_data",
            lines_before=["    l"] * 200,
            lines_after=["    l"] * 50,
            current_line="    result = ",
            cursor_position=13,
        )

        # 2. Extract features → bucket key
        bucket = extract_bucket_key(ctx)
        assert bucket.startswith("python:function:")

        # 3. Policy selects strategy (cold start → standard)
        policy = ThompsonSamplingPolicy()
        strategy_name = policy.select_strategy(bucket)
        assert strategy_name == "standard"

        # 4. Get strategy object
        strategy = get_strategy(strategy_name)
        assert strategy.max_tokens == 100

        # 5. Simulate feedback
        reward = compute_reward(accepted=True, latency_ms=500)
        assert reward > 0.5

        # 6. Update policy
        policy.update(bucket, strategy_name, reward)
        assert policy.total_interactions == 1

        params = policy._get_params(bucket, strategy_name)
        # standard starts at Beta(10, 1), after update with reward ≈ 0.925:
        # alpha = 10 + 0.925 ≈ 10.925, beta = 1 + 0.075 ≈ 1.075
        assert params[0] > 10.0
        assert params[1] > 1.0

    def test_persistence_flow(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            storage = PolicyStorage(policy_dir=tmpdir)

            # Simulate several interactions
            policy = ThompsonSamplingPolicy()
            for i in range(60):  # Past cold start
                policy.update("py:fn:med:mid", "standard", 0.8)

            storage.save(policy)

            # Load into new policy and verify
            policy2 = ThompsonSamplingPolicy()
            storage.load(policy2)
            assert policy2.total_interactions == 60

            # Should now be past cold start and able to explore
            # (though standard will still dominate due to strong posterior)
            strategy = policy2.select_strategy("py:fn:med:mid")
            assert strategy in STRATEGY_NAMES
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_strategy_selection_adapts(self):
        """After many positive updates for compact, it should be selected more often."""
        policy = ThompsonSamplingPolicy()
        bucket = "py:fn:small:mid"

        # Past cold start
        policy.total_interactions = COLD_START_THRESHOLD

        # Give compact many positive rewards
        for _ in range(100):
            policy.update(bucket, "compact", 1.0)
            policy.total_interactions = max(policy.total_interactions, COLD_START_THRESHOLD)

        # Give standard many negative rewards
        for _ in range(100):
            policy.update(bucket, "standard", 0.0)
            policy.total_interactions = max(policy.total_interactions, COLD_START_THRESHOLD)

        # Now compact should be selected more often than standard
        selections = []
        for _ in range(200):
            selections.append(policy.select_strategy(bucket))

        compact_count = selections.count("compact")
        standard_count = selections.count("standard")
        assert compact_count > standard_count


# ===========================================================================
# Strategy prompt construction tests
# ===========================================================================

class TestStrategyPromptConstruction:
    """Test that _build_user_prompt respects strategy parameters."""

    def _make_engine(self):
        """Create a SuggestionEngine with a mocked LLM."""
        with patch('vishwa.autocomplete.suggestion_engine.LLMFactory'):
            from vishwa.autocomplete.suggestion_engine import SuggestionEngine
            engine = SuggestionEngine.__new__(SuggestionEngine)
            engine.model = "test"
            engine.context_builder = MagicMock()
            engine.llm = None
            # We only need _build_user_prompt, not the full constructor
            from vishwa.autocomplete.context_builder import ContextBuilder
            engine.context_builder = ContextBuilder(context_lines=20)
            return engine

    def test_minimal_excludes_imports_and_functions(self):
        from vishwa.autocomplete.suggestion_engine import SuggestionEngine
        engine = self._make_engine()
        ctx = make_context(
            lines_before=["line" + str(i) for i in range(20)],
            lines_after=["after" + str(i) for i in range(5)],
        )
        ctx.imports = ["import os", "import sys"]
        ctx.referenced_functions = [FunctionInfo("foo", "def foo()", None, "pass")]

        strategy = get_strategy("minimal")
        prompt = engine._build_user_prompt(ctx, strategy=strategy)

        assert "# Imports:" not in prompt
        assert "# Available functions" not in prompt
        # Only last 5 lines before
        assert "line15" in prompt
        assert "line14" not in prompt  # line14 would be index 14, but with 20 lines, last 5 = 15,16,17,18,19
        # No lines after
        assert "# Code after cursor" not in prompt

    def test_standard_includes_imports_and_functions(self):
        engine = self._make_engine()
        ctx = make_context(
            lines_before=["line" + str(i) for i in range(20)],
            lines_after=["after" + str(i) for i in range(5)],
        )
        ctx.imports = ["import os"]
        ctx.referenced_functions = [FunctionInfo("foo", "def foo()", "A function", "pass")]

        strategy = get_strategy("standard")
        prompt = engine._build_user_prompt(ctx, strategy=strategy)

        assert "# Imports:" in prompt
        assert "import os" in prompt
        assert "# Available functions" in prompt
        assert "def foo()" in prompt

    def test_rich_includes_more_lines(self):
        engine = self._make_engine()
        ctx = make_context(
            lines_before=["line" + str(i) for i in range(30)],
            lines_after=["after" + str(i) for i in range(10)],
        )

        strategy = get_strategy("rich")
        prompt = engine._build_user_prompt(ctx, strategy=strategy)

        # Rich: 20 lines before, 5 lines after
        assert "line10" in prompt  # line at index 10 = 30-20=10th from start
        assert "after4" in prompt  # 5th line after (0-indexed)
        assert "after5" not in prompt  # Only 5 lines after

    def test_default_strategy_when_none(self):
        engine = self._make_engine()
        ctx = make_context()

        # Call without strategy → should use standard defaults
        prompt = engine._build_user_prompt(ctx)
        # Standard includes imports
        assert "# Imports:" in prompt
