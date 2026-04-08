/* =================================================================
   STRATEGY INTELLIGENCE UI VIEW MODEL
   Exposes: window.StrategyIntelligenceUI
   Requires: FMT
   ================================================================= */

window.StrategyIntelligenceUI = (() => {
  function issueTone(severity) {
    const value = String(severity || '').toLowerCase();
    if (value === 'critical' || value === 'high') return 'red';
    if (value === 'warning' || value === 'medium') return 'amber';
    if (value === 'ok' || value === 'low') return 'green';
    return 'muted';
  }

  function comparisonRows(comparison) {
    if (Array.isArray(comparison?.highlights) && comparison.highlights.length) {
      return comparison.highlights;
    }
    if (!comparison?.metrics) return [];
    return ['profit_percent', 'win_rate', 'profit_factor', 'max_drawdown']
      .map((key) => comparison.metrics[key])
      .filter(Boolean);
  }

  function suggestionGroups(intelligence) {
    const groups = intelligence?.suggestion_groups || {};
    const suggestions = Array.isArray(intelligence?.suggestions) ? intelligence.suggestions : [];
    const quickParams = Array.isArray(groups.quick_params)
      ? groups.quick_params
      : suggestions.filter((item) => item?.auto_applicable);
    const manualGuidance = Array.isArray(groups.manual_guidance)
      ? groups.manual_guidance
      : suggestions.filter((item) => !item?.auto_applicable);
    return { quickParams, manualGuidance };
  }

  function visibleIssues(diagnosis) {
    const primary = diagnosis?.primary || {};
    const issues = Array.isArray(diagnosis?.issues) ? diagnosis.issues : [];
    return issues.filter((issue) => {
      if (!issue) return false;
      const sameId = primary.id && issue.id && String(issue.id) === String(primary.id);
      const sameTitle = primary.title && issue.title && String(issue.title) === String(primary.title);
      return !sameId && !sameTitle;
    });
  }

  function metricSnapshotStats(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return [];
    const stats = [];
    if (FMT.toNumber(snapshot.total_trades) != null) {
      stats.push({ label: 'Trades', value: FMT.integer(snapshot.total_trades), tone: 'muted' });
    }
    if (FMT.toNumber(snapshot.win_rate_pct) != null) {
      stats.push({
        label: 'Win Rate',
        value: FMT.pct(snapshot.win_rate_pct, 1, false),
        tone: FMT.toneWinRate(snapshot.win_rate_pct),
      });
    }
    if (FMT.toNumber(snapshot.profit_factor) != null) {
      stats.push({
        label: 'Profit Factor',
        value: FMT.number(snapshot.profit_factor, 2),
        tone: FMT.toneRatio(snapshot.profit_factor, 1),
      });
    }
    if (FMT.toNumber(snapshot.total_profit_pct) != null) {
      stats.push({
        label: 'Return',
        value: FMT.pct(snapshot.total_profit_pct, 2, true),
        tone: FMT.toneProfit(snapshot.total_profit_pct),
      });
    }
    if (FMT.toNumber(snapshot.max_drawdown_pct) != null) {
      stats.push({
        label: 'Max Drawdown',
        value: FMT.pct(snapshot.max_drawdown_pct, 1, false),
        tone: FMT.toneDrawdown(snapshot.max_drawdown_pct),
      });
    }
    return stats;
  }

  function metricSnapshotText(snapshot) {
    return metricSnapshotStats(snapshot)
      .map((item) => `${item.label} ${item.value}`)
      .join(' · ');
  }

  function build(intelligence) {
    const diagnosis = intelligence?.diagnosis || {};
    const primary = diagnosis.primary || {};
    const issueCards = visibleIssues(diagnosis).map((issue) => ({
      title: issue.title || 'Issue',
      description: issue.explanation || issue.evidence || '',
      evidence: issue.evidence || '',
      tone: issueTone(issue.severity),
    }));
    const secondaryIssues = Array.isArray(diagnosis.secondary_issues) ? diagnosis.secondary_issues : [];
    const { quickParams, manualGuidance } = suggestionGroups(intelligence);
    const primaryStats = metricSnapshotStats(primary.metric_snapshot);

    return {
      primaryCard: {
        title: primary.title || 'Run diagnosis',
        explanation: primary.explanation || 'Review the issues and suggested next moves before rerunning.',
        evidence: primary.evidence || 'No metric-backed evidence was captured.',
        severity: primary.severity || 'neutral',
        severityTone: issueTone(primary.severity),
        confidence: primary.confidence || '',
        confidenceNote: primary.confidence_note || '',
      },
      primaryStats,
      issueCards: [
        ...issueCards,
        ...secondaryIssues.slice(0, 3).map((text) => ({
          title: 'Secondary Issue',
          description: String(text || ''),
          evidence: '',
          tone: 'amber',
        })),
      ],
      quickActionCards: quickParams.map((item) => ({
        title: item.title || 'Suggestion',
        description: item.description || '',
        evidence: item.evidence || '',
        tone: 'indigo',
        meta: item.parameter ? `Quick Params can apply ${item.parameter} = ${item.suggested_value}` : 'Available in Quick Params',
      })),
      manualGuidanceCards: manualGuidance.map((item) => ({
        title: item.title || 'Suggestion',
        description: item.description || '',
        evidence: item.evidence || '',
        tone: 'slate',
        meta: 'Manual follow-up. This stays advisory and does not change strategy code automatically.',
      })),
      summaryChips: [
        { label: `${quickParams.length} quick action${quickParams.length === 1 ? '' : 's'}` },
        { label: `${manualGuidance.length} manual item${manualGuidance.length === 1 ? '' : 's'}` },
      ],
    };
  }

  return {
    build,
    comparisonRows,
    issueTone,
    metricSnapshotText,
    suggestionGroups,
    visibleIssues,
  };
})();

