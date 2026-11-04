"""Explain chart values without presenting routing assumptions as measured accuracy."""
import json

AXES = (
    ('divergence', 'Creative exploration', 'Configured subjective rating; not a measured success rate.'),
    ('global_rigor', 'System-level reasoning', 'Configured subjective rating for architecture and broader reasoning.'),
    ('module_precision', 'Implementation precision', 'Configured subjective rating for local implementation and instruction following.'),
    ('capability', 'Vision and tools', 'Manual rating when set; otherwise the higher vision or GUI capability rating.'),
    ('economy', 'Quota economy', 'Decision view: quota and effort adjustments. Catalog view: estimated price economy.'),
)


def describe(series, models, source, plan=None):
    lines = ['HOW TO READ THIS COMPARISON',
             'Each spoke runs from 0 at the centre to 100 at the outer edge. These are routing ratings, not accuracy percentages.',
             'A larger polygon does not necessarily win. Task fit, ability requirements, harness, continuity, quota and effort affect the final ranking.',
             'The first three axes are configured judgments. They are not learned from your project outcomes.', '']
    for _, title, meaning in AXES:
        lines += [title + ': ' + meaning]
    lines += ['', 'DISPLAYED VALUES (0–100)']
    for row in series:
        lines += [row['label']]
        lines += [f"  {title}: {row.get('values', {}).get(key, 0) * 100:.0f}" for key, title, _ in AXES]
    lines += ['', 'CURRENT REFERENCE DATA',
              'This is the current model catalog, not a claim that historical decisions used this same revision.',
              f"Source: {source.get('source', 'unknown')}", f"Version: {source.get('version') or 'not recorded'}",
              f"Published: {source.get('published_at') or 'not recorded'}",
              f"File: {source.get('file') or 'not recorded'}",
              'Current score weights: ' + json.dumps(source.get('weights') or {}),
              'Current task-fit blend: ' + json.dumps(source.get('fit_blend') or {}), '',
              'Model basis notes below are supplied by the catalog. A benchmark reference does not establish every subjective rating.']
    for name, info in models.items():
        lines += ['', name, 'Subjective ratings: ' + json.dumps(info.get('subjective') or {}, ensure_ascii=False),
                  'User rating overrides: ' + json.dumps((source.get('overrides') or {}).get(name) or {}, ensure_ascii=False),
                  'Basis: ' + (info.get('basis') or 'No supporting basis recorded.'),
                  'Per-model measurement date: ' + str(info.get('measured_at') or 'not recorded')]
    if plan:
        lines += ['', 'DECISION RECOMPUTED WITH CURRENT QUOTA' if plan.get('theatre_source') == 'recomputed' else 'RECORDED DECISION', f"Selected candidate: {plan.get('choice') or 'none'}",
                  'The chart uses the recorded components below. Current catalog notes may differ from their original source.']
        for row in plan.get('ranking') or []:
            lines += ['', str(row.get('id')), f"Final score: {row.get('score')}",
                      'Exclusions: ' + '; '.join(row.get('excluded') or []),
                      'Components: ' + json.dumps(row.get('components') or {}, ensure_ascii=False, sort_keys=True)]
    return '\n'.join(lines)
