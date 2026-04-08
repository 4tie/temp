from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.services.results.strategy_intelligence_apply_service import apply_strategy_intelligence_suggestion


class StrategyIntelligenceApplyServiceTest(unittest.TestCase):
    def test_quick_apply_updates_sidecar_and_returns_retest_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / 'TestStrategy.py').write_text('class TestStrategy:\n    pass\n', encoding='utf-8')
            meta = {
                'strategy': 'TestStrategy',
                'strategy_class': 'TestStrategy',
                'strategy_path': None,
                'pairs': ['BTC/USDT'],
                'timeframe': '5m',
                'exchange': 'binance',
                'strategy_params': {'stoploss': -0.15},
            }
            results = {
                'strategy_intelligence': {
                    'suggestions': [
                        {
                            'id': 'param-1',
                            'title': 'Tighten stoploss',
                            'description': 'Reduce loss size',
                            'action_type': 'quick_param',
                            'parameter': 'stoploss',
                            'suggested_value': -0.08,
                        }
                    ]
                }
            }
            with patch('app.services.results.strategy_intelligence_apply_service.load_run_meta', return_value=meta), \
                patch('app.services.results.strategy_intelligence_apply_service.load_run_results', return_value=results), \
                patch('app.services.results.strategy_intelligence_apply_service.append_app_event'), \
                patch('app.services.results.strategy_intelligence_apply_service.resolve_strategy_source_path', return_value=strategies_dir / 'TestStrategy.py'), \
                patch('app.services.results.strategy_intelligence_apply_service.read_strategy_current_values', return_value={'stoploss': -0.15}), \
                patch('app.services.results.strategy_intelligence_apply_service.save_strategy_current_values') as save_params, \
                patch('app.services.results.strategy_intelligence_apply_service.build_strategy_sidecar_payload', side_effect=lambda strategy, values: {'strategy_name': strategy, 'params': {'sell': dict(values)}}):
                payload = asyncio.run(apply_strategy_intelligence_suggestion(run_id='run-1', suggestion_id='param-1'))

            save_params.assert_called_once()
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['strategy_params']['stoploss'], -0.08)
            self.assertFalse(payload['source_changed'])
            self.assertEqual(payload['retest_payload']['improvement_source'], 'strategy_intelligence_apply')

    def test_manual_apply_routes_through_ai_and_returns_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            py_path = strategies_dir / 'TestStrategy.py'
            py_path.write_text('class TestStrategy:\n    value = 1\n', encoding='utf-8')
            meta = {
                'strategy': 'TestStrategy',
                'strategy_class': 'TestStrategy',
                'strategy_path': None,
                'pairs': ['BTC/USDT'],
                'timeframe': '5m',
                'exchange': 'binance',
                'strategy_params': {'stoploss': -0.15},
            }
            results = {
                'strategy_intelligence': {
                    'diagnosis': {'primary': {'title': 'Weak entries', 'explanation': 'Bad timing', 'evidence': 'Win rate low'}},
                    'suggestions': [
                        {
                            'id': 'fix-1',
                            'title': 'Improve entries',
                            'description': 'Refine entry conditions',
                            'action_type': 'manual_guidance',
                            'apply_action': {'ai_apply_payload': {'title': 'Improve entries'}},
                        }
                    ]
                }
            }
            with patch('app.services.results.strategy_intelligence_apply_service.load_run_meta', return_value=meta), \
                patch('app.services.results.strategy_intelligence_apply_service.load_run_results', return_value=results), \
                patch('app.services.results.strategy_intelligence_apply_service.append_app_event'), \
                patch('app.services.results.strategy_intelligence_apply_service.resolve_strategy_source_path', return_value=py_path), \
                patch('app.services.results.strategy_intelligence_apply_service.read_strategy_source', return_value='class TestStrategy:\n    value = 1\n'), \
                patch('app.services.results.strategy_intelligence_apply_service.read_strategy_current_values', return_value={'stoploss': -0.15}), \
                patch('app.services.results.strategy_intelligence_apply_service.fetch_free_models', return_value=[{'id': 'model-a'}]), \
                patch('app.services.results.strategy_intelligence_apply_service.get_model_for_role', return_value=('model-a', 'test-reason')), \
                patch('app.services.results.strategy_intelligence_apply_service.chat_complete', return_value='```python\nclass TestStrategy:\n    value = 2\n```'), \
                patch('app.services.results.strategy_intelligence_apply_service.get_last_dispatch_meta', return_value={'provider': 'ollama', 'model': 'ollama/coder', 'fallback_used': True}), \
                patch('app.services.results.strategy_intelligence_apply_service.save_strategy_source', return_value={'bytes_written': 24}) as save_source:
                payload = asyncio.run(apply_strategy_intelligence_suggestion(run_id='run-2', suggestion_id='fix-1'))

            save_source.assert_called_once_with('TestStrategy', 'class TestStrategy:\n    value = 2')
            self.assertTrue(payload['source_changed'])
            self.assertTrue(payload['provider_meta']['fallback_used'])
            self.assertTrue(payload['diff_summary']['preview'])

    def test_manual_apply_rejects_external_strategy_path(self) -> None:
        meta = {
            'strategy': 'TestStrategy',
            'strategy_class': 'TestStrategy',
            'strategy_path': 'C:/external',
        }
        results = {
            'strategy_intelligence': {
                'suggestions': [
                    {'id': 'fix-1', 'action_type': 'manual_guidance', 'title': 'Improve entries'}
                ]
            }
        }
        with patch('app.services.results.strategy_intelligence_apply_service.load_run_meta', return_value=meta), \
            patch('app.services.results.strategy_intelligence_apply_service.load_run_results', return_value=results):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(apply_strategy_intelligence_suggestion(run_id='run-3', suggestion_id='fix-1'))
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
