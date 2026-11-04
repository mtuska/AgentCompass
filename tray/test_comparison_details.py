import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from comparison_details import describe


def test_sources_distinguish_current_catalog_from_recorded_decision():
    text = describe([{'label':'Example', 'values':{'divergence':.62}}],
        {'example':{'subjective':{'divergence':.62},'basis':'Reference claim'}},
        {'version':'abc','overrides':{'example':{'divergence':.62}}},
        {'choice':'example-medium','ranking':[{'id':'example-medium','score':.4,'components':{'fit':.7}}]})
    assert 'Creative exploration: 62' in text
    assert 'not accuracy percentages' in text
    assert 'not learned from your project outcomes' in text
    assert 'historical decisions used this same revision' in text
    assert 'Per-model measurement date: not recorded' in text
    assert 'Reference claim' in text
    assert 'User rating overrides' in text
    assert 'Final score: 0.4' in text
