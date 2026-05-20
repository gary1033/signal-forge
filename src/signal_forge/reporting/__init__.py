"""Reporting public API，依 artifact 類型拆出模組並保留舊匯入路徑。"""

from signal_forge.reporting.entry_edge import (
    write_entry_edge_comparison_outputs,
    write_entry_edge_outputs,
)
from signal_forge.reporting.paths import (
    EntryEdgeComparisonReportPaths,
    EntryEdgeReportPaths,
    PhaseReportPaths,
)
from signal_forge.reporting.phase import write_phase_outputs
from signal_forge.reporting.validators import (
    validate_phase_summary,
    validate_signal_digest_csv,
    validate_signal_digests,
    validate_trace_summary,
)

__all__ = [
    "EntryEdgeComparisonReportPaths",
    "EntryEdgeReportPaths",
    "PhaseReportPaths",
    "validate_phase_summary",
    "validate_signal_digest_csv",
    "validate_signal_digests",
    "validate_trace_summary",
    "write_entry_edge_comparison_outputs",
    "write_entry_edge_outputs",
    "write_phase_outputs",
]
